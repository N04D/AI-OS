from orchestrator.git import get_open_issues

def main():
    issues = get_open_issues()
    if issues:
        print("Open issues:")
        for issue in issues:
            print(f"  #{issue['number']}: {issue['title']}")
    else:
        print("No open issues found.")

if __name__ == "__main__":
    main()