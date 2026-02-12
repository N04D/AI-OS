from orchestrator.git import get_open_issues

def main():
    issues = get_open_issues()
    print("Open issues:")
    for issue in issues:
        print(f"  #{issue['number']}: {issue['title']}")

if __name__ == "__main__":
    main()
