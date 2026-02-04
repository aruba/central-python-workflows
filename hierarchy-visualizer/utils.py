"""Configuration hierarchy diagram generation module.

This module provides functionality to generate both static (GraphViz) and
interactive (Pyvis) visualizations of the configuration hierarchy.
"""

import os
import webbrowser
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class DiagramConfig:
    """Configuration options for diagram generation."""

    # Color scheme
    colors: Dict[str, str] = None

    # GraphViz settings
    graphviz_format: str = "png"
    graphviz_rankdir: str = "TB"
    graphviz_splines: str = "true"

    # Pyvis settings
    pyvis_height: str = "800px"
    pyvis_width: str = "100%"
    pyvis_bgcolor: str = "#222222"
    pyvis_font_color: str = "white"
    level_separation: int = 230
    node_spacing: int = 420
    tree_spacing: int = 460

    # Output settings
    auto_open_browser: bool = True

    def __post_init__(self):
        if self.colors is None:
            self.colors = {
                "Global": "#808080",
                "Site Collection": "#3FBC45",
                "Site": "#F5A623",
                "Access Points": "#E92012",
                "Switches": "#213CD3",
                "Gateways": "#9013FE",
                "Other Devices": "#BDBDBD",
            }


class DeviceClassifier:
    """Helper class for device classification and metadata extraction."""

    @staticmethod
    def normalize_device_type(device) -> str:
        """Normalize device type string."""
        device_type = getattr(device, "device_type", None) or "Unknown"
        return device_type.strip() or "Unknown"

    @staticmethod
    def get_device_category(device) -> str:
        """Categorize device based on its type.

        Returns one of: Access Points, Switches, Gateways, Other Devices
        """
        device_type = DeviceClassifier.normalize_device_type(device).upper()

        # Common Central values: "IAP", "AP", "ACCESS POINT", "SWITCH", "GATEWAY", "GW"
        if any(
            keyword in device_type
            for keyword in ("IAP", "AP", "ACCESS POINT", "ACCESS_POINT")
        ):
            return "Access Points"
        if "SWITCH" in device_type:
            return "Switches"
        if any(keyword in device_type for keyword in ("GATEWAY", "GW")):
            return "Gateways"
        return "Other Devices"

    @staticmethod
    def get_device_tooltip(device) -> str:
        """Generate tooltip text for a device."""
        device_type = DeviceClassifier.normalize_device_type(device)
        name = getattr(device, "name", None) or "Unknown"
        dev_id = getattr(device, "id", None)
        persona = getattr(device, "config_persona", None) or "N/A"
        return f"Type: {device_type}\nName: {name}\nID: {dev_id}\nFunction: {persona}"

    @staticmethod
    def get_device_label(device, include_id: bool = False) -> str:
        """Get display label for a device."""
        serial = getattr(device, "serial", None)
        name = getattr(device, "name", None)
        dev_id = getattr(device, "id", None)

        label = serial or name or f"dev_{dev_id}"
        if include_id and dev_id:
            label = f"{label}\n({dev_id})"
        return label


class GraphVizDiagramGenerator:
    """Generator for static GraphViz diagrams."""

    def __init__(self, config: Optional[DiagramConfig] = None):
        self.config = config or DiagramConfig()

    def generate(self, scopes, output_dir: str = ".") -> Optional[str]:
        """Generate a static hierarchy diagram using GraphViz.

        Args:
            scopes: Scopes object containing hierarchy data
            output_dir: Directory to save the output file (default: current directory)

        Returns:
            Path to generated file, or None if generation failed
        """
        try:
            from graphviz import Digraph
        except ImportError:
            print("\n⚠️ Graphical diagram failed: graphviz package missing")
            print("Install Graphviz: brew install graphviz && pip install graphviz")
            return None

        graph = Digraph("Configuration_Hierarchy", format=self.config.graphviz_format)
        graph.attr(
            rankdir=self.config.graphviz_rankdir, splines=self.config.graphviz_splines
        )

        # Build graph structure
        node_collections = self._build_graph_nodes(graph, scopes)
        self._add_graph_edges(graph, scopes, node_collections)
        self._apply_rank_constraints(graph, node_collections)

        # Render and save
        try:
            output_filename = os.path.join(output_dir, "hierarchy_diagram")
            output_path = graph.render(filename=output_filename, cleanup=True)
            return output_path
        except Exception as e:
            print(f"\n⚠️ Failed to render diagram: {e}")
            return None

    def _build_graph_nodes(self, graph, scopes) -> Dict[str, List[str]]:
        """Build all nodes and return collections for rank grouping."""
        collections = {
            "global": ["global"],
            "site_collections": [],
            "sites": [],
            "devices": [],
            "site_map": {},  # site_id -> node_id mapping
        }

        # Global node
        graph.node(
            "global",
            label=f"Global\n({getattr(scopes, 'id', 'global')})",
            shape="oval",
            style="filled",
            fillcolor="lightgrey",
        )

        # Site Collections
        for sc in getattr(scopes, "site_collections", []):
            sc_node = f"sc_{sc.id}"
            graph.node(
                sc_node,
                label=f"{sc.name}\n({sc.id})",
                shape="folder",
                style="filled",
                fillcolor="lightblue",
            )
            collections["site_collections"].append(sc_node)

        # Sites
        for site in getattr(scopes, "sites", []):
            site_node = f"site_{site.id}"
            graph.node(
                site_node,
                label=f"{site.name}\n({site.id})",
                shape="component",
                style="filled",
                fillcolor="lightyellow",
            )
            collections["sites"].append(site_node)
            collections["site_map"][str(site.id)] = site_node

        # Devices (only provisioned)
        for dev in getattr(scopes, "devices", []):
            if not getattr(dev, "provisioned_status", False):
                continue

            dev_node = f"dev_{dev.id}"
            device_type = DeviceClassifier.normalize_device_type(dev)
            serial = getattr(dev, "serial", "N/A")
            label = f"{serial}\n({dev.id})\n{device_type}"

            graph.node(
                dev_node,
                label=label,
                shape="box",
                style="rounded,filled",
                fillcolor="white",
            )
            collections["devices"].append(dev_node)

        return collections

    def _add_graph_edges(self, graph, scopes, collections: Dict):
        """Add edges between nodes."""
        site_map = collections["site_map"]
        sc_nodes = collections["site_collections"]

        # Global -> Site Collections
        for sc in getattr(scopes, "site_collections", []):
            graph.edge("global", f"sc_{sc.id}")

        # Site Collections -> Sites (or Global -> Sites)
        for site in getattr(scopes, "sites", []):
            site_node = f"site_{site.id}"
            parent_sc = getattr(site, "site_collection_id", None)

            if parent_sc is not None and f"sc_{parent_sc}" in sc_nodes:
                graph.edge(f"sc_{parent_sc}", site_node)
            else:
                graph.edge("global", site_node)

        # Sites -> Devices (or Global -> Devices)
        for dev in getattr(scopes, "devices", []):
            if not getattr(dev, "provisioned_status", False):
                continue

            dev_node = f"dev_{dev.id}"
            site_id = getattr(dev, "site_id", None)
            target = site_map.get(str(site_id)) if site_id else None

            if target:
                graph.edge(target, dev_node)

    def _apply_rank_constraints(self, graph, collections: Dict):
        """Force nodes into horizontal ranks for better layout."""
        for key in ["site_collections", "sites", "devices"]:
            nodes = collections.get(key, [])
            if nodes:
                with graph.subgraph() as subgraph:
                    subgraph.attr(rank="same")
                    for node in nodes:
                        subgraph.node(node)


class PyvisInteractiveDiagramGenerator:
    """Generator for interactive Pyvis HTML diagrams."""

    def __init__(self, config: Optional[DiagramConfig] = None):
        self.config = config or DiagramConfig()
        self.classifier = DeviceClassifier()

    def generate(self, scopes, output_dir: str = ".") -> Optional[str]:
        """Generate an interactive HTML diagram using Pyvis.

        Args:
            scopes: Scopes object containing hierarchy data
            output_dir: Directory to save the output file (default: current directory)

        Returns:
            Path to generated file, or None if generation failed
        """
        try:
            from pyvis.network import Network
        except ImportError:
            print("\n⚠️ Interactive diagram failed: pyvis package missing")
            print("Install: pip install pyvis")
            return None

        # Create and configure network
        net = self._create_network()

        # Prepare data structures
        devices = self._prepare_devices(scopes)
        sc_map, site_map = {}, {}

        # Build network (order matters for layout)
        self._add_devices(net, devices)
        self._add_sites(net, scopes, site_map)
        self._add_site_collections(net, scopes, sc_map)
        self._add_global_node(net, scopes)

        # Connect nodes
        self._add_edges(net, scopes, devices, sc_map, site_map)

        # Save and enhance HTML
        output_filename = os.path.join(output_dir, "hierarchy_interactive.html")
        return self._save_and_enhance(net, output_filename, devices)

    def _create_network(self):
        """Create and configure Pyvis Network object."""
        from pyvis.network import Network

        net = Network(
            height=self.config.pyvis_height,
            width=self.config.pyvis_width,
            directed=True,
            bgcolor=self.config.pyvis_bgcolor,
            font_color=self.config.pyvis_font_color,
        )

        # Configure hierarchical layout
        options = {
            "nodes": {"font": {"size": 28, "face": "Arial"}},
            "layout": {
                "hierarchical": {
                    "enabled": True,
                    "direction": "UD",
                    "sortMethod": "directed",
                    "levelSeparation": self.config.level_separation,
                    "nodeSpacing": self.config.node_spacing,
                    "treeSpacing": self.config.tree_spacing,
                }
            },
            "physics": {
                "hierarchicalRepulsion": {
                    "centralGravity": 0.0,
                    "springLength": 200,
                    "springConstant": 0.005,
                    "nodeDistance": 300,
                    "damping": 0.09,
                },
                "minVelocity": 0.75,
                "solver": "hierarchicalRepulsion",
            },
            "interaction": {
                "hover": True,
                "hoverConnectedEdges": True,
                "selectConnectedEdges": True,
                "navigationButtons": True,
                "keyboard": True,
                "zoomView": True,
            },
        }

        import json

        net.set_options(json.dumps(options))
        return net

    def _prepare_devices(self, scopes) -> List:
        """Get and sort provisioned devices."""
        devices = [
            dev
            for dev in getattr(scopes, "devices", [])
            if getattr(dev, "provisioned_status", False)
        ]

        return sorted(
            devices,
            key=lambda d: (
                getattr(d, "site_name", None) is None,
                getattr(d, "site_name", "") or "",
                self.classifier.normalize_device_type(d),
                getattr(d, "serial", "") or "",
                str(getattr(d, "id", "") or ""),
            ),
        )

    def _add_global_node(self, net, scopes):
        """Add global root node."""
        net.add_node(
            "global",
            label="Global",
            color=self.config.colors["Global"],
            shape="circle",
            size=60,
            level=0,
            title=f"ID: {getattr(scopes, 'id', 'global')}",
        )

    def _add_site_collections(self, net, scopes, sc_map: Dict):
        """Add site collection nodes."""
        site_collections = sorted(
            getattr(scopes, "site_collections", []), key=lambda sc: sc.id
        )

        for sc in site_collections:
            sc_id = f"sc_{sc.id}"
            sc_map[str(sc.id)] = sc_id
            net.add_node(
                sc_id,
                label=sc.name,
                color=self.config.colors["Site Collection"],
                shape="box",
                size=50,
                level=1,
                title=f"ID: {sc.id}",
            )

    def _add_sites(self, net, scopes, site_map: Dict):
        """Add site nodes."""
        sites = sorted(
            getattr(scopes, "sites", []),
            key=lambda s: (
                getattr(s, "site_collection_id", None) or float("inf"),
                s.id,
            ),
        )

        for site in sites:
            site_id = f"site_{site.id}"
            net.add_node(
                site_id,
                label=site.name,
                color=self.config.colors["Site"],
                shape="triangle",
                size=45,
                level=2,
                title=f"ID: {site.id}",
            )
            site_map[str(site.id)] = site_id

    def _add_devices(self, net, devices: List):
        """Add device nodes."""
        for dev in devices:
            dev_id = f"dev_{dev.id}"
            category = self.classifier.get_device_category(dev)
            label = self.classifier.get_device_label(dev)
            tooltip = self.classifier.get_device_tooltip(dev)

            net.add_node(
                dev_id,
                label=label,
                color=self.config.colors.get(
                    category, self.config.colors["Other Devices"]
                ),
                shape="dot",
                size=40,
                level=3,
                title=tooltip,
            )

    def _add_edges(self, net, scopes, devices: List, sc_map: Dict, site_map: Dict):
        """Add all edges between nodes."""
        # Global -> Site Collections
        for sc in getattr(scopes, "site_collections", []):
            sc_node_id = sc_map.get(str(sc.id))
            if sc_node_id:
                net.add_edge("global", sc_node_id)

        # Site Collections -> Sites (or Global -> Sites)
        for site in getattr(scopes, "sites", []):
            site_node_id = site_map.get(str(site.id))
            if not site_node_id:
                continue

            parent_sc_id = getattr(site, "site_collection_id", None)
            if parent_sc_id is not None:
                parent_node = sc_map.get(str(parent_sc_id), "global")
            else:
                parent_node = "global"
            net.add_edge(parent_node, site_node_id)

        # Sites -> Devices (or Global -> Devices)
        for dev in devices:
            dev_node_id = f"dev_{dev.id}"
            device_site_id = getattr(dev, "site_id", None)
            parent_node = (
                site_map.get(str(device_site_id)) if device_site_id else None
            ) or "global"
            net.add_edge(parent_node, dev_node_id)

    def _save_and_enhance(self, net, output_file: str, devices: List) -> Optional[str]:
        """Save network and add legend to HTML.

        Returns:
            Path to output file if successful, None otherwise
        """
        try:
            net.save_graph(output_file)
            self._add_legend_to_html(output_file, devices)
            
            output_path =  os.path.abspath(output_file)
            # Compute relative path for terminal output
            rel_output_path = os.path.relpath(output_path, os.getcwd())
            
            if self.config.auto_open_browser:
                webbrowser.open(f"file://{output_path}")

            return rel_output_path
        except Exception as e:
            print(f"\n⚠️ Could not generate interactive diagram: {e}")
            print(
                "Try reinstalling pyvis: pip install --upgrade --force-reinstall pyvis"
            )
            return None

    def _add_legend_to_html(self, output_file: str, devices: List):
        """Add color legend to HTML file."""
        # Determine which device categories are present
        present_categories = {self.classifier.get_device_category(d) for d in devices}

        legend_order = [
            "Global",
            "Site Collection",
            "Site",
            "Access Points",
            "Switches",
            "Gateways",
        ]
        if "Other Devices" in present_categories:
            legend_order.append("Other Devices")

        # Build legend HTML
        legend_items = "\n".join(
            f"<div style='display:flex;align-items:center;margin:6px 0;'>"
            f"<span style='display:inline-block;width:20px;height:20px;"
            f"background:{self.config.colors[name]};border:1px solid #111;margin-right:10px;'></span>"
            f"<span style='color:#fff;font-family:Arial,sans-serif;font-size:17px;'>{name}</span>"
            f"</div>"
            for name in legend_order
        )

        legend_html = (
            "<div id='pyvis-legend' style='position:fixed;top:16px;right:16px;"
            "background:rgba(0,0,0,0.6);padding:12px 14px;border-radius:8px;"
            "z-index:9999;max-height:70vh;overflow:auto;'>"
            "<div style='color:#fff;font-family:Arial,sans-serif;font-size:18px;"
            "font-weight:bold;margin-bottom:8px;'>Legend</div>"
            f"{legend_items}"
            "</div>"
        )

        layout_tweak_css = (
            "<style>"
            "#mynetwork{margin-top:-60px;}"
            "</style>"
        )

        center_global_script = (
            "<script>"
            "window.addEventListener('load', function(){"
            "setTimeout(function(){"
            "if (typeof network !== 'undefined') {"
            "network.fit({animation: {duration: 0}});"
            "var pos = network.getPositions(['global'])['global'];"
            "if (pos) {"
            "var scale = network.getScale();"
            "network.moveTo({position: pos, scale: scale, animation: {duration: 0}});"
            "}"
            "}"
            "}, 150);"
            "});"
            "</script>"
        )

        # Insert legend into HTML
        with open(output_file, "r", encoding="utf-8") as f:
            html = f.read()

        if "id='pyvis-legend'" not in html:
            if "</body>" in html:
                html = html.replace("</body>", f"{legend_html}\n</body>")
            else:
                html = f"{html}\n{legend_html}\n"

        if "#mynetwork{margin-top:-60px;}" not in html:
            if "</head>" in html:
                html = html.replace("</head>", f"{layout_tweak_css}\n</head>")
            else:
                html = f"{layout_tweak_css}\n{html}"

        if "network.focus('global'" not in html:
            if "</body>" in html:
                html = html.replace("</body>", f"{center_global_script}\n</body>")
            else:
                html = f"{html}\n{center_global_script}\n"

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html)


# Convenience functions for backward compatibility
def generate_diagram(
    scopes, config: Optional[DiagramConfig] = None, output_dir: str = "."
) -> Optional[str]:
    """Generate a static GraphViz diagram.

    Args:
        scopes: Scopes object containing hierarchy data
        config: Optional configuration for diagram appearance
        output_dir: Directory to save the output file (default: current directory)

    Returns:
        Path to generated file, or None if generation failed
    """
    generator = GraphVizDiagramGenerator(config)
    return generator.generate(scopes, output_dir=output_dir)


def generate_interactive_diagram(
    scopes, config: Optional[DiagramConfig] = None, output_dir: str = "."
) -> Optional[str]:
    """Generate an interactive Pyvis HTML diagram.

    Args:
        scopes: Scopes object containing hierarchy data
        config: Optional configuration for diagram appearance
        output_dir: Directory to save the output file (default: current directory)

    Returns:
        Path to generated file, or None if generation failed
    """
    generator = PyvisInteractiveDiagramGenerator(config)
    return generator.generate(scopes, output_dir=output_dir)
