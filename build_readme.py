import feedparser
import httpx
import json
import os
import pathlib
from python_graphql_client import GraphqlClient
import re


root = pathlib.Path(__file__).parent.resolve()
client = GraphqlClient(endpoint="https://api.github.com/graphql")


TOKEN = os.environ.get("TOKEN", "")
# TOKEN = ""
# with open("token", "r") as f:
#     TOKEN = f.read()

def replace_chunk(content, marker, chunk, inline=False):
    r = re.compile(
        r"<!\-\- {} starts \-\->.*<!\-\- {} ends \-\->".format(marker, marker),
        re.DOTALL,
    )
    if not inline:
        chunk = "\n{}\n".format(chunk)
    chunk = "<!-- {} starts -->{}<!-- {} ends -->".format(marker, chunk, marker)
    return r.sub(chunk, content)


organization_graphql = """
  organization(login: "rpicluster") {
    repositories(first: 100, privacy: PUBLIC) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        name
        description
        url
        releases(orderBy: {field: CREATED_AT, direction: DESC}, first: 1) {
          totalCount
          nodes {
            name
            publishedAt
            url
          }
        }
      }
    }
  }
"""

def make_query(after_cursor=None, include_organization=False):
    return """
query {
  ORGANIZATION
  viewer {
    repositories(first: 100, privacy: PUBLIC, after: AFTER) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        name
        description
        url
        releases(orderBy: {field: CREATED_AT, direction: DESC}, first: 1) {
          totalCount
          nodes {
            name
            publishedAt
            url
          }
        }
      }
    }
  }
}
""".replace(
        "AFTER", '"{}"'.format(after_cursor) if after_cursor else "null"
    ).replace(
        "ORGANIZATION", organization_graphql if include_organization else "",
    )



def fetch_releases(oauth_token):
    repos = []
    releases = []
    repo_names = {"playing-with-actions"}  # Skip this one
    has_next_page = True
    after_cursor = None

    first = True

    while has_next_page:
        data = client.execute(
            query=make_query(after_cursor, include_organization=True),
            headers={"Authorization": "Bearer {}".format(oauth_token)},
        )
        first = False
        print()
        print(json.dumps(data, indent=4))
        print()
        repo_nodes = data["data"]["viewer"]["repositories"]["nodes"]
        if "organization" in data["data"]:
            repo_nodes += data["data"]["organization"]["repositories"]["nodes"]
        for repo in repo_nodes:
            if repo["releases"]["totalCount"] and repo["name"] not in repo_names:
                repos.append(repo)
                repo_names.add(repo["name"])
                releases.append(
                    {
                        "repo": repo["name"],
                        "repo_url": repo["url"],
                        "description": repo["description"],
                        "release": repo["releases"]["nodes"][0]["name"]
                        .replace(repo["name"], "")
                        .strip(),
                        "published_at": repo["releases"]["nodes"][0]["publishedAt"],
                        "published_day": repo["releases"]["nodes"][0][
                            "publishedAt"
                        ].split("T")[0],
                        "url": repo["releases"]["nodes"][0]["url"],
                        "total_releases": repo["releases"]["totalCount"],
                        "length": 3 + len(repo["name"]) + 1 + len(repo["releases"]["nodes"][0]["name"].replace(repo["name"], "").strip()) + 2 + 
                        len(repo["url"]) + 1 + len(repo["releases"]["nodes"][0]["publishedAt"].split("T")[0])
                    }
                )
        after_cursor = data["data"]["viewer"]["repositories"]["pageInfo"]["endCursor"]
        has_next_page = after_cursor
    releases.sort(key=lambda r: r["published_at"], reverse=True)
    mx = -1
    for release in releases[:5]:
        if release["length"] > mx:
            mx = release["length"]
    for release in releases[:5]:
        release["spaces"] = " " * (mx - release["length"])
    return releases


if __name__ == "__main__":
    readme = root / "README.md"
    releases = fetch_releases(TOKEN)
    md = "\n".join(
        [
            "* [{repo} {release}]({url}){spaces} - {published_day}".format(**release)
            for release in releases[:5]
        ]
    )
    readme_contents = readme.open().read()
    rewritten = replace_chunk(readme_contents, "recent_releases", md)
    readme.open("w").write(rewritten)
