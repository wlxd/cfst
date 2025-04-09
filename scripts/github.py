import requests
import concurrent.futures
import re
import time
from urllib.parse import urlparse, parse_qs

class GitHubScanner:
    def __init__(self, token=None):
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHubLinkScanner/3.0"
        }
        self.excluded_files = {'license.txt', 'requirements.txt', 'support.txt', 'readme.txt'}
        self.allowed_ext = {'.txt', '.yaml'}
        if token:
            self.headers["Authorization"] = f"token {token}"
        self.link_cache = {}

    def get_repo_tree(self, repo_url):
        parts = repo_url.replace("https://github.com/", "").split("/")
        if len(parts) < 2:
            return []
        owner, repo = parts[0], parts[1]
        try:
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1",
                headers=self.headers,
                timeout=15
            )
            response.raise_for_status()
            return response.json().get("tree", [])
        except:
            return []

    def is_special_link(self, url):
        if url in self.link_cache:
            if time.time() < self.link_cache[url]["expiry"]:
                return self.link_cache[url]
        
        parsed = urlparse(url)
        result = {"url": url, "is_special": False, "valid": False, "reason": []}

        path_matches = re.findall(r'\b[a-zA-Z0-9]{24,}\b', parsed.path)
        if path_matches:
            result["is_special"] = True
            result["reason"].append(f"长路径参数: {path_matches[-1]}")

        query_params = parse_qs(parsed.query)
        sensitive_params = {'token', 'key', 'secret', 'auth'}
        for param in query_params:
            if param.lower() in sensitive_params and len(query_params[param][0]) >= 16:
                result["is_special"] = True
                result["reason"].append(f"敏感参数: {param}")

        if result["is_special"]:
            try:
                resp = requests.head(url, allow_redirects=True, timeout=10)
                result["valid"] = resp.status_code == 200
            except:
                result["valid"] = False
            
            self.link_cache[url] = result
            self.link_cache[url]["expiry"] = time.time() + 600

        return result

def scan_repository(repo_url, scanner):
    result = {"repo": repo_url, "raw_links": [], "special_links": []}
    try:
        tree_data = scanner.get_repo_tree(repo_url)
        valid_files = [
            f for f in tree_data 
            if f["type"] == "blob" 
            and f["path"].split(".")[-1].lower() in {'txt', 'yaml'}
            and f["path"].split("/")[-1].lower() not in scanner.excluded_files
        ]

        result["raw_links"] = [
            f"https://raw.githubusercontent.com/{repo_url.split('github.com/')[-1]}/main/{f['path']}"
            for f in valid_files
        ]

        readme_files = [f for f in tree_data if f["path"].lower() == "readme.md"]
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for f in readme_files:
                raw_url = f"https://raw.githubusercontent.com/{repo_url.split('github.com/')[-1]}/main/{f['path']}"
                futures.append(executor.submit(requests.get, raw_url, timeout=10))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    content = future.result().text
                    links = re.findall(r'https?://[^\s)\]\'"]+', content)
                    for url in links:
                        analysis = scanner.is_special_link(url)
                        if analysis["is_special"] and analysis["valid"]:
                            result["special_links"].append({
                                "url": url,
                                "reasons": analysis["reason"]
                            })
                except:
                    continue
    except:
        pass
    return result

def main_search(keyword, token=None):
    scanner = GitHubScanner(token)
    try:
        response = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": f"{keyword} in:name,description,readme", "sort": "updated", "order": "desc", "per_page": 100},
            headers=scanner.headers,
            timeout=20
        )
        repos = [item["html_url"] for item in response.json()["items"]]
    except:
        return []
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(scan_repository, repo, scanner): repo for repo in repos}
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    
    filtered_results = []
    for res in results:
        valid_raw = len(res["raw_links"]) > 0
        valid_special = len(res["special_links"]) > 0
        if not valid_raw and not valid_special:
            continue
        
        filtered_res = {"repo": res["repo"]}
        if valid_raw:
            filtered_res["raw_links"] = res["raw_links"]
        if valid_special:
            filtered_res["special_links"] = res["special_links"]
        filtered_results.append(filtered_res)
    
    return filtered_results

if __name__ == "__main__":
    results = main_search("节点")
    for res in results:
        print(f"\n仓库: {res['repo']}")
        if "raw_links" in res:
            print("合规文件:")
            for link in res["raw_links"]:
                print(link)
        if "special_links" in res:
            print("特殊链接:")
            for link in res["special_links"]:
                print(link["url"])