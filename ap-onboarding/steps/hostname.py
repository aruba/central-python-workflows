from pycentral.utils.url_utils import generate_url

from steps.models import AddOnStep, Field
from utils.profile_ops import set_local_profile_field

SYSTEM_INFO_PATH = generate_url("system-info/sys-system-info-profile")


def set_hostname(device, hostname):
    return set_local_profile_field(
        device, SYSTEM_INFO_PATH, "hostname", hostname, "hostname"
    )


STEP = AddOnStep(
    key="hostname",
    label="Hostname",
    description="Set the device hostname after provisioning.",
    field=Field(
        type="string",
        required=False,
        max_len=63,
        pattern=r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
        help="Use 1-63 letters, numbers, or hyphens; start and end with a letter or number.",
        example="store-3-ap",
    ),
    run=set_hostname,
)
