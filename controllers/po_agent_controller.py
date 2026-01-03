# controllers/po_agent_controller.py
import re
import datetime
from datetime import timedelta
from services.bedrock_service import BedrockService
from services.supplierx_api import SupplierXAPI

# States
STATE_PO_TYPE = "PO_TYPE"
STATE_SUPPLIER = "SUPPLIER"
STATE_SUPPLIER_DETAILS = "SUPPLIER_DETAILS"
STATE_ORG_DETAILS = "ORG_DETAILS"
STATE_COMMERCIALS = "COMMERCIALS"
STATE_LINE_ITEM_DETAILS = "LINE_ITEM_DETAILS"
STATE_CONFIRM = "CONFIRM"
STATE_DONE = "DONE"

class POAgent:
    def __init__(self):
        self.api = SupplierXAPI()
        self.nlu = BedrockService()

    def get_initial_state(self):
        return {
            "current_step": STATE_PO_TYPE,
            "payload": {
                "line_items": [],
                "projects": [{"project_code": "", "project_name": ""}],
                "currency": "INR",
                "alternate_supplier_name": "",
                "alternate_supplier_email": "",
                "alternate_supplier_contact_number": "",
                "validityEnd": "",
                "is_epcg_applicable": False,
                "remarks": "",
                "inco_terms_description": "",
                "payment_terms_description": "",
                "is_pr_based": False,
                "is_rfq_based": False,
                "noc": "No",
                "datasupplier": ""
            },
            "temp_data": {}
        }

    def process(self, user_text: str, state: dict) -> str:
        payload = state["payload"]
        response_parts = []

        lower_text = user_text.lower().strip()

        # === Direct API Listing Commands with DEBUG PRINTS ===
        if lower_text.startswith(("list ", "show ", "what are ", "give me ", "display ", "tell me the ")):
            print(f"\n[DEBUG] User requested listing: '{user_text}'")

            if any(kw in lower_text for kw in ["purchase org", "purchase organization", "purchase organisations", "orgs", "purchasing org"]):
                print("[API CALL] → get_purchase_orgs()")
                orgs = self.api.get_purchase_orgs()
                print(f"[API RESPONSE] ← Returned {len(orgs) if orgs else 0} purchase organizations")
                if not orgs:
                    return "No purchase organizations found."
                lines = [f"**Purchase Organizations ({len(orgs)} found):**\n"]
                for o in orgs[:25]:
                    lines.append(f"• {o['name']} (ID: {o['id']})")
                if len(orgs) > 25:
                    lines.append(f"\n... and {len(orgs)-25} more.")
                return "\n".join(lines)

            elif "plant" in lower_text:
                print("[DEBUG] User asked about plants")

                # Prefer already selected org
                if payload.get("purchase_org_id"):
                    org_id = payload["purchase_org_id"]
                    org_name = payload.get("purchase_org_name", "Selected Organization")
                    plants = self.api.get_plants([org_id])
                    print(f"[API CALL] → get_plants() for selected org ID {org_id}")
                    print(f"[API RESPONSE] ← {len(plants)} plants")
                    if not plants:
                        return f"No plants found for **{org_name}**."
                    lines = [f"**Plants for {org_name} ({len(plants)} found):**\n"]
                    for p in plants[:20]:
                        lines.append(f"• {p['name']} (Code: {p.get('code', 'N/A')}, ID: {p['id']})")
                    if len(plants) > 20:
                        lines.append(f"\n... and {len(plants)-20} more.")
                    return "\n".join(lines)

                # Fallback: try to extract org from message
                orgs = self.api.get_purchase_orgs()
                specified_org = max(orgs, key=lambda o: match_ratio(o["name"], user_text), default=None)
                if specified_org and match_ratio(specified_org["name"], user_text) > 0.4:
                    plants = self.api.get_plants([specified_org["id"]])
                    lines = [f"**Plants for {specified_org['name']} ({len(plants)} found):**\n"]
                    for p in plants[:20]:
                        lines.append(f"• {p['name']} (Code: {p.get('code', 'N/A')}, ID: {p['id']})")
                    return "\n".join(lines)

                # Last fallback: sample from a few orgs
                return "Please select a Purchase Organization first, or try 'list purchase organizations'."

            elif any(kw in lower_text for kw in ["purchase group", "group", "purchasing group"]):
                print("[DEBUG] User asked about purchase groups")

                if payload.get("purchase_org_id"):
                    org_id = payload["purchase_org_id"]
                    org_name = payload.get("purchase_org_name", "Selected Organization")
                    groups = self.api.get_purchase_groups([org_id])
                    print(f"[API CALL] → get_purchase_groups() for selected org ID {org_id}")
                    print(f"[API RESPONSE] ← {len(groups)} groups")
                    if not groups:
                        return f"No groups found for **{org_name}**."
                    lines = [f"**Purchase Groups for {org_name} ({len(groups)} found):**\n"]
                    for g in groups[:25]:
                        lines.append(f"• {g['name']} (ID: {g['id']})")
                    if len(groups) > 25:
                        lines.append(f"\n... and {len(groups)-25} more.")
                    return "\n".join(lines)

                # Fallback similar to plants
                orgs = self.api.get_purchase_orgs()
                specified_org = max(orgs, key=lambda o: match_ratio(o["name"], user_text), default=None)
                if specified_org and match_ratio(specified_org["name"], user_text) > 0.4:
                    groups = self.api.get_purchase_groups([specified_org["id"]])
                    lines = [f"**Purchase Groups for {specified_org['name']} ({len(groups)} found):**\n"]
                    for g in groups[:25]:
                        lines.append(f"• {g['name']} (ID: {g['id']})")
                    return "\n".join(lines)

                return "Please select a Purchase Organization first, or try 'list purchase organizations'."

                

            elif any(kw in lower_text for kw in ["supplier", "vendors"]):
                print("[API CALL] → search_suppliers(limit=30)")
                suppliers = self.api.search_suppliers(limit=30)
                print(f"[API RESPONSE] ← Returned {len(suppliers) if suppliers else 0} suppliers")
                if not suppliers:
                    return "No suppliers found."
                lines = [f"**Suppliers ({len(suppliers)} shown):**\n"]
                for s in suppliers:
                    lines.append(f"• {s['name']} (ID: {s['vendor_id']})")
                return "\n".join(lines)

            elif any(kw in lower_text for kw in ["project"]):
                print("[API CALL] → get_projects()")
                projects = self.api.get_projects()
                print(f"[API RESPONSE] ← Returned {len(projects) if projects else 0} projects")
                if not projects:
                    return "No projects available."
                lines = [f"**Projects ({len(projects)}):**\n"]
                for p in projects[:25]:
                    lines.append(f"• {p['project_name']} (Code: {p['project_code']})")
                if len(projects) > 25:
                    lines.append(f"\n... and {len(projects)-25} more.")
                return "\n".join(lines)

            elif any(kw in lower_text for kw in ["payment term", "payment"]):
                print("[API CALL] → get_payment_terms()")
                terms = self.api.get_payment_terms()
                print(f"[API RESPONSE] ← Returned {len(terms) if terms else 0} payment terms")
                if not terms:
                    return "No payment terms found."
                lines = [f"**Payment Terms ({len(terms)}):**\n"]
                for t in terms[:20]:
                    lines.append(f"• {t['name']} (ID: {t['id']})")
                return "\n".join(lines)

            elif any(kw in lower_text for kw in ["incoterm", "inco term", "inco"]):
                print("[API CALL] → get_incoterms()")
                terms = self.api.get_incoterms()
                print(f"[API RESPONSE] ← Returned {len(terms) if terms else 0} incoterms")
                if not terms:
                    return "No incoterms found."
                lines = [f"**Incoterms ({len(terms)}):**\n"]
                for t in terms[:20]:
                    lines.append(f"• {t['name']} (ID: {t['id']})")
                return "\n".join(lines)

            elif any(kw in lower_text for kw in ["po type", "po sub type", "po types"]):
                print("[INFO] No API call - using static get_po_sub_types()")
                types = self.api.get_po_sub_types()
                return f"**Available PO Types:**\n" + "\n".join([f"• {t}" for t in types])

            elif any(kw in lower_text for kw in ["material", "item"]):
                print("[API CALL] → get_materials()")
                mats = self.api.get_materials()
                print(f"[API RESPONSE] ← Returned {len(mats) if mats else 0} materials")
                if not mats:
                    return "No materials loaded."
                lines = [f"**Sample Materials ({len(mats)} total):**\n"]
                for m in mats[:25]:
                    lines.append(f"• {m['name']} (ID: {m['id']}, Price: ₹{m.get('price', 'N/A')})")
                if len(mats) > 25:
                    lines.append(f"\n... and {len(mats)-25} more.")
                return "\n".join(lines)

        # === END OF LISTING COMMANDS ===

        # Always run NLU
        nlu_result = self.nlu.analyze_intent(user_text, state["current_step"])
        entities = nlu_result.get("entities", {})

        # Global create PO trigger
        if re.search(r"\b(create po|submit|finalize|done|create the po|make the po)\b", user_text, re.I):
            if payload.get("line_items"):
                return self._submit_po(payload, state)
            return "❌ Please add at least one line item before creating the PO."

        progressed = True
        while progressed:
            progressed = False
            current_step = state["current_step"]

            if current_step == STATE_PO_TYPE:
                po_sub_type = entities.get("po_sub_type")
                if not po_sub_type:
                    lower_text = user_text.lower()
                    for pt in self.api.get_po_sub_types():
                        if pt.lower() in lower_text:
                            po_sub_type = pt
                            break

                if po_sub_type:
                    po_type_map = {
                        "regular purchase": "regularPurchase",
                        "service": "service",
                        "asset": "asset",
                    }
                    payload["po_type"] = po_type_map.get(po_sub_type.lower(), "regularPurchase")
                    state["current_step"] = STATE_SUPPLIER
                    response_parts.append(f"Selected **{po_sub_type}**.")
                    progressed = True

            elif current_step == STATE_SUPPLIER:
                supplier_name = entities.get("supplier_name")
                if not supplier_name:
                    match = re.search(r"(?:for|from|supplier[:\s]+)([a-zA-Z\s.&()]+?)(?:\.|,|$|\s+po)", user_text, re.I)
                    if match:
                        supplier_name = match.group(1).strip()

                if supplier_name:
                    results = self.api.search_suppliers(supplier_name, limit=5)
                    if results:
                        sup = results[0]
                        payload["vendor_id"] = sup["vendor_id"]
                        alt = self.api.get_alternate_supplier_details(sup["vendor_id"])
                        payload.update(alt)
                        payload["currency"] = self.api.get_currencies()[0]
                        state["current_step"] = STATE_SUPPLIER_DETAILS
                        response_parts.append(f"Supplier selected: **{sup['name']}**.")
                        progressed = True
                    else:
                        return f"Could not find supplier '{supplier_name}'. Try 'list suppliers' to see available ones."

            elif current_step == STATE_SUPPLIER_DETAILS:
                date_pattern = r"(\d{1,2})\s*(?:st|nd|rd|th)?\s*([a-zA-Z]+)\s*(\d{4})"
                dates = re.findall(date_pattern, user_text, re.I)

                po_date = None
                validity = None

                if dates:
                    try:
                        day, month_name, year = dates[0]
                        po_date = datetime.datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y").strftime("%Y-%m-%d")
                    except:
                        po_date = datetime.date.today().strftime("%Y-%m-%d")

                    if len(dates) > 1:
                        try:
                            day, month_name, year = dates[-1]
                            validity = datetime.datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y").strftime("%Y-%m-%d")
                        except:
                            validity = (datetime.datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                    else:
                        validity = (datetime.datetime.strptime(po_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")

                if po_date:
                    payload["po_date"] = po_date
                    payload["validityEnd"] = validity
                    state["current_step"] = STATE_ORG_DETAILS
                    response_parts.append(f"PO Date: **{po_date}**, Validity until: **{validity}**.")
                    progressed = True

            elif current_step == STATE_ORG_DETAILS:
                user_lower = user_text.lower()

                # Load organizations once
                orgs = self.api.get_purchase_orgs()

                def match_ratio(api_name, user_text):
                    api_words = set(api_name.lower().split())
                    user_words = set(user_text.lower().split())
                    if not api_words or not user_words:
                        return 0
                    intersection = api_words.intersection(user_words)
                    return len(intersection) / len(api_words.union(user_words))

                # --- Match Purchase Organization ---
                best_org = max(orgs, key=lambda o: match_ratio(o["name"], user_text), default=None)
                if best_org and match_ratio(best_org["name"], user_text) > 0.4:
                    payload["purchase_org_id"] = best_org["id"]
                    payload["purchase_org_name"] = best_org["name"]   # ← important for context
                    response_parts.append(f"✅ Purchase Org: **{best_org['name']}**")
                else:
                    # If no match, don't wipe existing org if already set
                    if "purchase_org_id" not in payload:
                        response_parts.append("Could not identify Purchase Organization. Try 'list purchase organizations' to see exact names.")
                        # Do NOT progress further if org is missing
                        response = "\n".join(response_parts) if response_parts else "Please specify the Purchase Organization."
                        return response

                # --- Fetch plants and groups for the selected org ---
                plants = self.api.get_plants([payload["purchase_org_id"]])
                groups = self.api.get_purchase_groups([payload["purchase_org_id"]])

                # --- Match Plant (by name or by short code like IP09) ---
                best_plant = None
                # First try exact code match (e.g., IP09, IM07)
                plant_code_match = re.search(r'\b([A-Z]{2}\d{2})\b', user_text.upper())
                if plant_code_match:
                    code = plant_code_match.group(1)
                    best_plant = next((p for p in plants if p.get("code") == code), None)

                # Fallback to fuzzy name match
                if not best_plant and plants:
                    best_plant = max(plants, key=lambda p: match_ratio(p["name"], user_text), default=None)
                    if best_plant and match_ratio(best_plant["name"], user_text) <= 0.3:
                        best_plant = None

                if best_plant:
                    payload["plant_id"] = best_plant["id"]
                    response_parts.append(f"✅ Plant: **{best_plant['name']}** (Code: {best_plant.get('code', 'N/A')})")

                # --- Match Purchase Group ---
                best_group = None
                if groups:
                    best_group = max(groups, key=lambda g: match_ratio(g["name"], user_text), default=None)
                    if best_group and match_ratio(best_group["name"], user_text) > 0.3:
                        payload["purchase_grp_id"] = best_group["id"]
                        response_parts.append(f"✅ Purchase Group: **{best_group['name']}**")

                # --- Check if we have everything ---
                required = ["purchase_org_id", "plant_id", "purchase_grp_id"]
                missing = [r.replace("_id", "").title() for r in required if r not in payload]

                if not missing:
                    state["current_step"] = STATE_COMMERCIALS
                    progressed = True
                else:
                    response_parts.append(f"ℹ️ Could not confidently match: {', '.join(missing)}. "
                                          f"You can say 'list plants' or 'list groups' to see options.")
                    

            elif current_step == STATE_COMMERCIALS:
                projects = self.api.get_projects()
                if projects:
                    payload["projects"][0].update(projects[0])
                pay_terms = self.api.get_payment_terms()
                if pay_terms:
                    payload["payment_terms"] = pay_terms[0]["id"]
                inco_terms = self.api.get_incoterms()
                if inco_terms:
                    payload["inco_terms"] = inco_terms[0]["id"]
                payload["remarks"] = "Created via AI Agent"
                state["current_step"] = STATE_LINE_ITEM_DETAILS
                state["temp_data"] = {"new_item": {}}
                response_parts.append("Commercials configured.")
                progressed = True

            elif current_step == STATE_LINE_ITEM_DETAILS:
                qty_match = re.search(r"(\d+)\s+(?:x|X|×)?\s*([a-zA-Z\s.&()]+?)(?:\s+at|@|₹|\s+each|\s+price)", user_text, re.I)
                price_match = re.search(r"₹\s*([\d,]+)", user_text)

                if qty_match and price_match:
                    material_name = qty_match.group(2).strip().lower()
                    qty = int(qty_match.group(1))
                    price = float(price_match.group(1).replace(",", ""))

                    is_regular = payload.get("po_type") == "regularPurchase"
                    if is_regular:
                        materials = self.api.get_materials(material_name)
                        if materials:
                            m = materials[0]
                            sub_total = qty * price
                            delivery_date = (
                                datetime.datetime.strptime(payload.get("po_date", datetime.date.today().strftime("%Y-%m-%d")), "%Y-%m-%d")
                                + timedelta(days=7)
                            ).strftime("%Y-%m-%d")

                            item = {
                                "short_text": m["name"],
                                "short_desc": m["name"],
                                "quantity": qty,
                                "unit_id": m.get("unit_id", 1),
                                "price": price,
                                "sub_total": sub_total,
                                "tax": 12,
                                "total_value": sub_total + 12,
                                "delivery_date": delivery_date,
                                "material_id": m["id"],
                                "material_group_id": m.get("material_group_id", 520),
                                "tax_code": m.get("tax_code", 118),
                                "subServices": "",
                                "control_code": "",
                            }

                            payload["line_items"].append(item)
                            response_parts.append(
                                f"Added **{qty} × {m['name']}** at ₹{price} each (Subtotal: ₹{sub_total})"
                            )
                            state["current_step"] = STATE_CONFIRM
                            progressed = True
                        else:
                            return f"Could not find material '{material_name}'. Try 'list materials' or a different name."
                    else:
                        # Service PO logic
                        item = {
                            "short_text": material_name.title(),
                            "quantity": qty,
                            "price": price,
                            "sub_total": qty * price,
                            "tax": 12,
                            "total_value": qty * price + 12,
                            "delivery_date": payload.get("po_date", datetime.date.today().strftime("%Y-%m-%d")),
                            "subServices": "",
                            "control_code": "",
                            "short_desc": material_name.title()
                        }
                        payload["line_items"].append(item)
                        response_parts.append(f"Added service: **{qty} × {material_name.title()}** at ₹{price} each.")
                        state["current_step"] = STATE_CONFIRM
                        progressed = True

        # Final response assembly
        if response_parts:
            response = "\n".join(response_parts)
            if state["current_step"] == STATE_CONFIRM:
                total = sum(item.get("sub_total", 0) for item in payload["line_items"])
                response += f"\n\n**Order Summary:**\n"
                for i, item in enumerate(payload["line_items"], 1):
                    response += f"{i}. {item['short_text']} — {item['quantity']} × ₹{item['price']} = ₹{item['sub_total']}\n"
                response += f"\n**Grand Total:** ₹{total}\n\nReady to **create the PO**? Say 'create PO' or add more items."
            elif state["current_step"] == STATE_LINE_ITEM_DETAILS:
                response += "\n\nWhat items would you like to purchase? (e.g., '2 laptops at ₹50000 each')"
        else:
            # Helpful fallback
            step_names = {
                STATE_SUPPLIER: "supplier name",
                STATE_SUPPLIER_DETAILS: "PO date and validity",
                STATE_ORG_DETAILS: "purchase organization, plant, and group",
                STATE_LINE_ITEM_DETAILS: "line items (material/service, quantity, price)"
            }
            response = f"Please provide the {step_names.get(state['current_step'], 'next detail')}."

        return response


    def _submit_po(self, payload: dict, state: dict) -> str:
        total = sum(item.get("sub_total", 0) for item in payload["line_items"])
        payload["total"] = total

        # Clean line items
        for item in payload["line_items"]:
            item["subServices"] = ""
            item["control_code"] = ""

        result = self.api.create_po(payload)

        if result.get("success") == True or result.get("error") == False:
            po_num = result.get("po_number", result.get("data", {}).get("po_number", "Unknown"))
            state["current_step"] = STATE_DONE
            return f"✅ **Purchase Order Created Successfully!**\n\n**PO Number:** {po_num}\n**Total Value:** ₹{total}"
        else:
            msg = result.get("message", "Unknown error")
            if isinstance(result.get("details"), dict):
                msg += f" | {result['details']}"
            return f"❌ Failed to create PO.\n\nError: {msg}"