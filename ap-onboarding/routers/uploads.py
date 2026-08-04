import csv
import io

import yaml
from fastapi import APIRouter, File, HTTPException, UploadFile

import steps

router = APIRouter()


@router.post("/api/parse-upload")
async def parse_upload(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename or ""

    try:
        if filename.endswith(".csv"):
            text = content.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            devices = []
            application_names = set()
            for row in reader:
                device: dict = {}
                if row.get("serial_number"):
                    device["serial_number"] = row["serial_number"].strip()
                for step in steps.STEPS:
                    raw_value = row.get(step.key)
                    if raw_value is None:
                        continue
                    value = raw_value.strip()
                    if not value:
                        continue
                    if step.field.type == "string":
                        device[step.key] = value
                    elif step.field.type == "bool":
                        device[step.key] = value.lower() not in ("false", "0", "no")
                    elif step.field.type == "int":
                        try:
                            device[step.key] = int(value)
                        except ValueError as exc:
                            raise ValueError(
                                f"Invalid integer in column '{step.key}' "
                                f"at CSV line {reader.line_num}: {value!r}"
                            ) from exc
                    elif step.field.type == "list[string]":
                        device[step.key] = [
                            item.strip() for item in value.split(",") if item.strip()
                        ]
                    else:
                        raise ValueError(
                            f"Unsupported type '{step.field.type}' "
                            f"for column '{step.key}'"
                        )
                if row.get("site"):
                    device["site"] = row["site"].strip()
                if row.get("device_function"):
                    device["device_function"] = row["device_function"].strip()
                if row.get("device_group"):
                    device["device_group"] = row["device_group"].strip()
                if row.get("model"):
                    device["model"] = row["model"].strip()
                if row.get("mac"):
                    device["mac"] = row["mac"].strip()
                glp = row.get("glp_onboarding", "").strip().lower()
                if glp:
                    device["glp_onboarding"] = glp not in ("false", "0", "no")
                if row.get("subscription_key"):
                    device["subscription_key"] = row["subscription_key"].strip()
                if device.get("serial_number"):
                    application_name = (row.get("application_name") or "").strip()
                    if application_name:
                        application_names.add(application_name)
                    devices.append(device)
            if len(application_names) > 1:
                names = sorted(application_names)
                found = ", ".join(repr(name) for name in names[:-1])
                if found:
                    found += f" and {names[-1]!r}"
                else:
                    found = repr(names[-1])
                raise ValueError(
                    "Column 'application_name' must name one GLP application "
                    f"for the whole file; found {found}."
                )
            defaults = {}
            if application_names:
                application_name = next(iter(application_names))
                defaults["application_assignment"] = {"name": application_name}
            return {"defaults": defaults, "sites": [], "device_groups": [], "configuration_profiles": [], "devices": devices}

        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ValueError("Expected a YAML mapping")
        return {
            "defaults": data.get("defaults") or {},
            "sites": data.get("sites") or [],
            "device_groups": data.get("device_groups") or [],
            "configuration_profiles": data.get("configuration_profiles") or [],
            "devices": data.get("devices") or [],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}")
