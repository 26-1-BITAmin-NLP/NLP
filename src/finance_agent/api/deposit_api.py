from finance_agent.api.finance_api_utils import call_api, save_raw_json

deposit_params = {
    "topFinGrpNo": "020000",
    "pageNo": 1
}

deposit = call_api("/depositProductsSearch.json", deposit_params)
save_raw_json(deposit, "src/finance_agent/data/raw/deposit.json")