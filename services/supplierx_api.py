# services/supplierx_api.py
import requests
import os
from dotenv import load_dotenv
from typing import List
load_dotenv()

BASE_URL = "https://dev.api.supplierx.aeonx.digital"
API_TOKEN = os.getenv("SUPPLIERX_API_TOKEN")
SESSION_KEY = os.getenv("SUPPLIERX_SESSION_KEY")

class SupplierXAPI:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "x-session-key": SESSION_KEY,
            "Content-Type": "application/json"
        }

    def _post(self, endpoint: str, payload: dict = None):
        url = f"{BASE_URL}{endpoint}"
        try:
            response = requests.post(url, headers=self.headers, json=payload or {})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API Error ({endpoint}): {e}")
            if hasattr(e, 'response'):
                try:
                    return e.response.json()
                except:
                    return {"error": True, "message": str(e), "details": e.response.text}
            return {"error": True, "message": str(e)}

    def _get(self, endpoint: str):
        url = f"{BASE_URL}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API Error ({endpoint}): {e}")
            return {"error": True, "message": str(e)}

    def get_po_sub_types(self):
        return [
            "Regular Purchase", "Service", "Asset", "Internal Order Material",
            "Internal Order Service", "Network", "Network Service",
            "Cost Center Material", "Cost Center Service", "Project Service",
            "Project Material", "Stock Transfer Inter", "Stock Transfer Intra"
        ]

    def search_suppliers(self, query: str = None, limit: int = 10):
        payload = {"search": query} if query else {}
        data = self._post("/api/v1/supplier/supplier/sapRegisteredVendorsList", payload)
        items = data.get("data", []) if isinstance(data, dict) else []
        return [
            {
                "vendor_id": str(item["id"]),
                "sap_code": str(item.get("sap_code", "")),
                "name": item.get("supplier_name", "")
            }
            for item in items[:limit]
        ]

    def get_alternate_supplier_details(self, vendor_id: str):
        data = self._get(f"/api/v1/supplier/supplier/additional-supplier-details/{vendor_id}")
        alt = (data.get("data", []) or [{}])[0]
        return {
            "alternate_supplier_name": alt.get("alternate_supplier_name", ""),
            "alternate_supplier_email": alt.get("alternate_supplier_email", ""),
            "alternate_supplier_contact_number": alt.get("alternate_supplier_contact_number", "")
        }

    # def get_currencies(self):
    #     data = self._post("/api/v1/admin/currency/getWithoutSlug", {})
    #     items = data.get("data", []) if isinstance(data, dict) else []
    #     return [item.get("currencyCode", "INR") for item in items][:1] or ["INR"]
    def get_currencies(self):
        data = self._post("/api/v1/admin/currency/getWithoutSlug", {})
        
        items = []
        if isinstance(data, dict) and "data" in data:
            items = data["data"]
        elif isinstance(data, list):
            items = data
        
        # Handle both cases: list of dicts OR list of strings
        currencies = []
        for item in items:
            if isinstance(item, dict):
                currencies.append(item.get("currencyCode", item.get("id", "INR")))
            elif isinstance(item, str):
                currencies.append(item)
        
        return currencies[:1] or ["INR"]

    def get_purchase_orgs(self):
        data = self._post("/api/v1/supplier/purchaseOrg/listing", {})
        rows = data.get("data", {}).get("rows", []) if isinstance(data, dict) else []
        return [{"id": item["id"], "name": item.get("description", "")} for item in rows]

    def get_plants(self, org_ids: List[int] = None):
        payload = {"dropdown": "0"}
        if org_ids:
            payload["purchase_org_id"] = org_ids

        print(f"[API CALL] → POST /api/v1/admin/plants/list with payload: {payload}")
        data = self._post("/api/v1/admin/plants/list", payload)
        print(f"[API RESPONSE] ← Raw plants response: {type(data)} with keys: {data.keys() if isinstance(data, dict) else 'list'}")

        plants = []
        if isinstance(data, dict):
            if data.get("error") == False and "data" in data:
                plants = data["data"]
        elif isinstance(data, list):
            plants = data  # direct list

        # Normalize
        normalized = []
        for p in plants:
            if isinstance(p, dict):
                normalized.append({
                    "id": p.get("id"),
                    "code": p.get("code"),
                    "name": p.get("name", ""),
                    "location": p.get("location", "")
                })

        print(f"[API RESULT] ← Returning {len(normalized)} plants")
        return normalized

    def get_purchase_groups(self, org_ids: List[int]):
        payload = {"dropdown": "0"}
        if org_ids:
            payload["purchase_org_id"] = org_ids

        data = self._post("/api/v1/admin/purchaseGroup/list", payload)

        # Same robust extraction
        rows = []
        if isinstance(data, dict):
            if "data" in data:
                inner = data["data"]
                if isinstance(inner, dict) and "rows" in inner:
                    rows = inner["rows"]
                elif isinstance(inner, list):
                    rows = inner
        elif isinstance(data, list):
            rows = data

        if not isinstance(rows, list):
            rows = []

        return [
            {"id": item.get("id"), "name": item.get("name") or item.get("description", "")}
            for item in rows
            if isinstance(item, dict)
        ]

    def get_projects(self):
        data = self._post("/api/v1/supplier/purchase-order/list-project", {})
        rows = data.get("data", {}).get("rows", []) if isinstance(data, dict) else []
        return [{"project_code": item.get("projectCode"), "project_name": item.get("projectName")} for item in rows]

    def get_payment_terms(self):
        data = self._post("/api/admin/paymentTerms/list", {})
        rows = data.get("data", {}).get("rows", []) if isinstance(data, dict) else []
        return [{"id": item["id"], "name": item.get("description", "")} for item in rows]

    def get_incoterms(self):
        data = self._post("/api/admin/IncoTerm/list", {})
        rows = data.get("data", {}).get("rows", []) if isinstance(data, dict) else []
        return [{"id": item["id"], "name": item.get("description", "")} for item in rows]

    def get_materials(self, query: str = None):
        payload = {"search": query} if query else {}
        data = self._post("/api/v1/supplier/materials/list", payload)
        rows = data.get("data", {}).get("rows", []) if isinstance(data, dict) else []
        return [
            {
                "id": item["id"],
                "name": item.get("name", ""),
                "price": float(item.get("price", 0)),
                "unit_id": int((item.get("unit") or {}).get("id", 0)),
                "material_group_id": int((item.get("material_group") or {}).get("id", 520)),
                "tax_code": 118
            }
            for item in rows
        ]

    def create_po(self, payload: dict):
        # Flatten for form-data
        def flatten(d, parent_key=''):
            items = {}
            for k, v in d.items():
                new_key = f"{parent_key}.{k}" if parent_key else k
                if isinstance(v, dict):
                    items.update(flatten(v, new_key))
                elif isinstance(v, list):
                    for i, val in enumerate(v):
                        items.update(flatten(val, f"{new_key}[{i}]"))
                else:
                    items[new_key] = "" if v is None else str(v).lower() if isinstance(v, bool) else str(v)
            return items

        flat = flatten(payload)
        multipart = {k: (None, v) for k, v in flat.items()}
        headers = self.headers.copy()
        headers.pop("Content-Type", None)

        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/supplier/purchase-order/create",
                headers=headers,
                files=multipart
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "error": True, "message": str(e)}