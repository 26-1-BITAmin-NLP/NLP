from finance_agent.processing import parse_all_products, filter
from finance_agent.printer import print_report
from finance_agent.llm import generate_report

def main():

    # 상품 데이터 정리
    products = parse_all_products()

    # 사용자 조건 필터링
    user_condition = {}
    
    filtered = filter(products, user_condition)

    # LLM 의견서 생성
    report = generate_report(filtered, user_condition)

    # 출력
    print_report(report)

if __name__ == "__main__":
    main()
