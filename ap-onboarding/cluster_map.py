CLUSTER_MAP = {
    "US-1":        {"new_central": "us1.api.central.arubanetworks.com",       "classic": "https://app1-apigw.central.arubanetworks.com"},
    "US-2":        {"new_central": "us2.api.central.arubanetworks.com",       "classic": "https://apigw-prod2.central.arubanetworks.com"},
    "US-East1":    {"new_central": "us6.api.central.arubanetworks.com",       "classic": "https://apigw-us-east-1.central.arubanetworks.com"},
    "US-West4":    {"new_central": "us4.api.central.arubanetworks.com",       "classic": "https://apigw-uswest4.central.arubanetworks.com"},
    "US-West5":    {"new_central": "us5.api.central.arubanetworks.com",       "classic": "https://apigw-uswest5.central.arubanetworks.com"},
    "EU-1":        {"new_central": "de1.api.central.arubanetworks.com",       "classic": "https://eu-apigw.central.arubanetworks.com"},
    "EU-Central2": {"new_central": "de2.api.central.arubanetworks.com",       "classic": "https://apigw-eucentral2.central.arubanetworks.com"},
    "EU-Central3": {"new_central": "de3.api.central.arubanetworks.com",       "classic": "https://apigw-eucentral3.central.arubanetworks.com"},
    "UK":          {"new_central": "gb1.api.central.arubanetworks.com",       "classic": "https://apigw-ukwest2.central.arubanetworks.com"},
    "Canada-1":    {"new_central": "ca1.api.central.arubanetworks.com",       "classic": "https://apigw-ca.central.arubanetworks.com"},
    "APAC-1":      {"new_central": "in1.api.central.arubanetworks.com",       "classic": "https://api-ap.central.arubanetworks.com"},
    "APAC-EAST1":  {"new_central": "jp1.api.central.arubanetworks.com",       "classic": "https://apigw-apaceast.central.arubanetworks.com"},
    "APAC-SOUTH1": {"new_central": "au1.api.central.arubanetworks.com",       "classic": "https://apigw-apacsouth.central.arubanetworks.com"},
    "UAE":         {"new_central": "ae1.api.central.arubanetworks.com",       "classic": "https://apigw-uaenorth1.central.arubanetworks.com"},
    "China":       {"new_central": "cn1.api.central.arubanetworks.com.cn",    "classic": "https://apigw.central.arubanetworks.com.cn"},
    "Internal":    {"new_central": "internal.api.central.arubanetworks.com",  "classic": "https://internal-apigw.central.arubanetworks.com/"},
}


def cluster_key_from_base_url(base_url: str, side: str) -> str | None:
    if not base_url:
        return None
    normalized = base_url.rstrip("/").lower()
    for key, urls in CLUSTER_MAP.items():
        if urls[side].rstrip("/").lower() == normalized:
            return key
    return None
