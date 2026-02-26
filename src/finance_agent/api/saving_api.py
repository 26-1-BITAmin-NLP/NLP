from finance_agent.api.finance_api_utils import call_api, save_raw_json

saving_params = {
    "topFinGrpNo": "020000",
    "pageNo": 1
}

saving = call_api("/savingProductsSearch.json", saving_params)
save_raw_json(saving, "src/finance_agent/data/raw/saving.json")