from finance_agent.api.finance_api_utils import call_api, save_raw_json

rentloan_params = {
    "topFinGrpNo": "020000",
    "pageNo": 1
}

rentloan = call_api("/rentHouseLoanProductsSearch.json", rentloan_params)
save_raw_json(rentloan, "src/finance_agent/data/raw/rentloan.json")