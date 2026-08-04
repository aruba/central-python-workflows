export const CLUSTER_KEYS = [
  "US-1",
  "US-2",
  "US-East1",
  "US-West4",
  "US-West5",
  "EU-1",
  "EU-Central2",
  "EU-Central3",
  "UK",
  "Canada-1",
  "APAC-1",
  "APAC-EAST1",
  "APAC-SOUTH1",
  "UAE",
  "China",
  "Internal",
] as const;

export type ClusterKey = (typeof CLUSTER_KEYS)[number];

export interface ClusterEndpoints {
  newCentral: string;
  classicCentral: string;
}

export const CLUSTER_ENDPOINTS: Record<ClusterKey, ClusterEndpoints> = {
  "US-1": {
    newCentral: "us1.api.central.arubanetworks.com",
    classicCentral: "https://app1-apigw.central.arubanetworks.com",
  },
  "US-2": {
    newCentral: "us2.api.central.arubanetworks.com",
    classicCentral: "https://apigw-prod2.central.arubanetworks.com",
  },
  "US-East1": {
    newCentral: "us6.api.central.arubanetworks.com",
    classicCentral: "https://apigw-us-east-1.central.arubanetworks.com",
  },
  "US-West4": {
    newCentral: "us4.api.central.arubanetworks.com",
    classicCentral: "https://apigw-uswest4.central.arubanetworks.com",
  },
  "US-West5": {
    newCentral: "us5.api.central.arubanetworks.com",
    classicCentral: "https://apigw-uswest5.central.arubanetworks.com",
  },
  "EU-1": {
    newCentral: "de1.api.central.arubanetworks.com",
    classicCentral: "https://eu-apigw.central.arubanetworks.com",
  },
  "EU-Central2": {
    newCentral: "de2.api.central.arubanetworks.com",
    classicCentral: "https://apigw-eucentral2.central.arubanetworks.com",
  },
  "EU-Central3": {
    newCentral: "de3.api.central.arubanetworks.com",
    classicCentral: "https://apigw-eucentral3.central.arubanetworks.com",
  },
  UK: {
    newCentral: "gb1.api.central.arubanetworks.com",
    classicCentral: "https://apigw-ukwest2.central.arubanetworks.com",
  },
  "Canada-1": {
    newCentral: "ca1.api.central.arubanetworks.com",
    classicCentral: "https://apigw-ca.central.arubanetworks.com",
  },
  "APAC-1": {
    newCentral: "in1.api.central.arubanetworks.com",
    classicCentral: "https://api-ap.central.arubanetworks.com",
  },
  "APAC-EAST1": {
    newCentral: "jp1.api.central.arubanetworks.com",
    classicCentral: "https://apigw-apaceast.central.arubanetworks.com",
  },
  "APAC-SOUTH1": {
    newCentral: "au1.api.central.arubanetworks.com",
    classicCentral: "https://apigw-apacsouth.central.arubanetworks.com",
  },
  UAE: {
    newCentral: "ae1.api.central.arubanetworks.com",
    classicCentral: "https://apigw-uaenorth1.central.arubanetworks.com",
  },
  China: {
    newCentral: "cn1.api.central.arubanetworks.com.cn",
    classicCentral: "https://apigw.central.arubanetworks.com.cn",
  },
  Internal: {
    newCentral: "internal.api.central.arubanetworks.com",
    classicCentral: "https://internal-apigw.central.arubanetworks.com/",
  },
};

export function isClusterKey(value: string): value is ClusterKey {
  return CLUSTER_KEYS.some((cluster) => cluster === value);
}
