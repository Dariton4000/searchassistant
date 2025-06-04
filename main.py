import lmstudio as lms
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from duckduckgo_search import DDGS
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
import re

# Todo:
# - pause .act during question asking, so that the user can answer the question and then continue with the next step.
# - add Wikipedia search functionality
# - add better next_step handling for example when current step is not correct
# - add ability for researcher to modify the research plan, for example to add new steps or remove existing ones
# - add function to save final report with markdown into /final_report directory with date and time in the filename



def next_step(results: str) -> str:
    """Keeps track of plan progress and returns the next step without user input."""
    plan_file = Path("research_plans") / "plan.json"
    state_file = Path("research_plans") / "state.json"

    # Load the plan
    try:
        with plan_file.open("r") as f:
            plan_data = json.load(f)
            steps = [plan_data[k] for k in sorted(plan_data.keys(), key=int)]
    except (FileNotFoundError, json.JSONDecodeError):
        print("Plan file missing or invalid.")
        return "Cannot determine next step."

    # Load or initialize progress state
    try:
        with state_file.open("r") as f:
            curr = json.load(f).get("current_step", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        curr = 0

    # If this isn’t the first call, report results of the last step
    if curr > 0 and curr <= len(steps):
        last = steps[curr - 1]
        print(f"Results of Step {curr} ({last}): {results}")

    # Move to the next step
    next_num = curr + 1
    if next_num <= len(steps):
        next_step_text = steps[next_num - 1]
        print(f"Next Step ({next_num}): {next_step_text}")
        # Save updated progress
        with state_file.open("w") as f:
            json.dump({"current_step": next_num}, f)
        return next_step_text
    else:
        print("Research plan complete.")
        return "Research plan complete."
    
def get_current_step() -> str:
    """Returns the current step number and its description."""
    plan_file = Path("research_plans") / "plan.json"
    state_file = Path("research_plans") / "state.json"
    try:
        with state_file.open("r") as f:
            curr = json.load(f).get("current_step", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return "No current step set."
    try:
        with plan_file.open("r") as f:
            data = json.load(f)
            steps = [data[k] for k in sorted(data.keys(), key=int)]
    except (FileNotFoundError, json.JSONDecodeError):
        return "Research plan not found or invalid."
    if curr <= 0 or curr > len(steps):
        return "No current step available."
    return f"Step {curr}: {steps[curr - 1]}"

def get_all_steps() -> list:
    """Returns all steps in the research plan."""
    plan_file = Path("research_plans") / "plan.json"
    if not plan_file.exists():
        return []
    with plan_file.open("r") as f:
        try:
            data = json.load(f)
            return [data[key] for key in sorted(data.keys(), key=int)]
        except json.JSONDecodeError:
            return []

def ask_question(question: str):
    """Asks the user a question about the research task."""
    print(question)
    qanswer = input("Your answer: ")
    if not qanswer:
        return "No answer provided. Make an assumption."
    else:
        return qanswer
    #fix later, please

def create_research_plan_step(step: str) -> str:
    """Adds a new step to the research plan."""
    plan_file = Path("research_plans") / "plan.json"
    # load existing or start fresh
    if plan_file.exists():
        with plan_file.open("r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}
    # determine next numeric key
    nums = [int(k) for k in data.keys() if k.isdigit()]
    next_num = max(nums, default=0) + 1
    data[str(next_num)] = step
    # write back
    with plan_file.open("w") as f:
        json.dump(data, f, indent=2)
    print(f"Step {next_num} created: {step}")
    return f"Step {next_num} created successfully."

def save_knowledge(knowledge: str) -> str:
    """Adds new knowledge for later use."""
    knowledge_file = Path("research_knowledge") / "knowledge.json"
    # load existing or start fresh
    if knowledge_file.exists():
        with knowledge_file.open("r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}
    # determine next numeric key
    nums = [int(k) for k in data.keys() if k.isdigit()]
    next_num = max(nums, default=0) + 1
    data[str(next_num)] = knowledge
    # write back
    with knowledge_file.open("w") as f:
        json.dump(data, f, indent=2)
    print(f"Knowledge {next_num} saved: {knowledge}")
    return f"Knowledge {next_num} saved successfully."

def get_all_knowledge() -> list:
    """Returns all entries in the knowledge base."""
    knowledge_file = Path("research_knowledge") / "knowledge.json"
    if not knowledge_file.exists():
        return []
    with knowledge_file.open("r") as f:
        try:
            data = json.load(f)
            return [data[key] for key in sorted(data.keys(), key=int)]
        except json.JSONDecodeError:
            return []

def print_fragment(fragment, round_index=0):
    # .act() supplies the round index as the second parameter
    # Setting a default value means the callback is also
    # compatible with .complete() and .respond().
    print(fragment.content, end="", flush=True)

def duckduckgo_search(search_query: str) -> str:
    """Searches DuckDuckGo for the given query and returns the results.

    Args:
        query: The query to search for.
        treat it like a google search query
    Returns:
        The search results and crawlable links.
    """
    print(f"\nSearching DuckDuckGo for: {search_query}...")
    results = DDGS().text(search_query, max_results=4)
    print(results)
    return json.dumps(results)


def get_wikipedia_page(page: str) -> str:
    """
    Get content from a Wikipedia page.
    If no exact match is found, it will return a list of simular pages.
    
    Args:
        page: Exact title of the Wikipedia page
            
    Returns:
        Page content as plain text
    """
    url = 'https://en.wikipedia.org/w/api.php'
    params = {
        'action': 'query',
        'format': 'json',
        'prop': 'extracts',
        'explaintext': True,
        'titles': page
    }
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    pages = data.get('query', {}).get('pages', {})
        
    if not pages:
        result = "No page found."
    else:
        page_data = next(iter(pages.values()))
        result = page_data.get('extract', "No content found for the given page.")
    
    # Note: Context will be displayed after the full response is complete
    return result

async def crawl4aiasync(url: str):
    browser_conf = BrowserConfig(headless=True)  # or False to see the browser
    run_conf = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS
    )

    async with AsyncWebCrawler(config=browser_conf) as crawler:
        result = await crawler.arun(
            url=url,
            config=run_conf
        )
        return(result.markdown)

def create_report(title: str, content: str, sources: list) -> str:
    """Generates a final report in markdown format.

    Args:
        title: The title of the report. Will also be used for the file name combined with the current date and time for a unique file name.
        content: The content of the report.
        sources: A list of sources used in the report.
    Saves:
        The final report in markdown format into reports/.
    Returns:
        The file name of the report for the AI to tell the user where to find it or an error message.
    """
    # Validate and sanitize title
    sanitized_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
    if not sanitized_title:
        return "Error: Report title cannot be empty or contain only special characters."

    report_content = f"# {sanitized_title}\n\n{content}\n\n## Sources\n"
    for source in sources:
        report_content += f"- {source}\n"

    reports_dir = Path("reports")
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / f"{sanitized_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with report_file.open("w") as f:
            f.write(report_content)
        print(f"Report saved to {report_file}")
        return f"Report saved to {report_file}"
    except IOError as e:
        error_message = f"Error writing report to file: {e}"
        print(error_message)
        return error_message

def crawl4ai(url: str):
    """Crawls a given URL and returns the text content.

    Args:
        url: The URL to crawl.
        needs to start with http:// or https://
    Returns:
        The text content of the page in markdown format.
    """
    print(f"Crawling {url}...")
    return asyncio.run(crawl4aiasync(url))

def researcher():
    model = lms.llm()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chat = lms.Chat(
        f"You are a task-focused AI researcher. The current date and time is {now}. Begin researching immediately and continue until every step of the plan is complete. Perform multiple online searches to gather reliable information. After visiting a webpage, store any useful knowledge in the research knowledge base. Recall stored knowledge before moving to the next step and when drafting the final report. Produce the report in markdown format using the create_report tool."
    )
    steps = get_all_steps()
    first_step_text = f"Here is the first step of the research plan:\n{steps[0]}\nAfter completing this step, move on to the next step. Dont forget to save all knowledge you find in the research knowledge base. Recall all knowledge you have saved when compiling a final report."
    chat.add_user_message(first_step_text)

    print("Bot: ", end="", flush=True)
    model.act(
        chat,
        [next_step, get_current_step, duckduckgo_search, get_all_steps, save_knowledge, get_all_knowledge, crawl4ai, create_report, get_wikipedia_page],
        on_message=chat.append,
        on_prediction_fragment=print_fragment,
    )
    print()

    # Now enter the interactive loop
    while True:
        try:
            user_input = input("You (leave blank to exit): ")
        except EOFError:
            print()
            break
        if not user_input:
           break
        chat.add_user_message(user_input)
        print("Bot: ", end="", flush=True)
        model.act(
            chat,
            [next_step, get_current_step, duckduckgo_search, get_all_steps, save_knowledge, get_all_knowledge, crawl4ai, create_report, get_wikipedia_page],
            on_message=chat.append,
            on_prediction_fragment=print_fragment,
        )
        print()





def main():
    research_topic = input("Please provide a research task for the ai researcher: ")
    PLAN_DIR = Path("research_plans")   # Directory to store research plans
    PLAN_DIR.mkdir(exist_ok=True)   # Create the directory if it doesn't exist
    KNOWLEDGE_DIR = Path("research_knowledge")   # Directory to store research knowledge
    KNOWLEDGE_DIR.mkdir(exist_ok=True)   # Create the directory if it doesn't exist
    REPORT_DIR = Path("reports")   # Directory to store final reports
    REPORT_DIR.mkdir(exist_ok=True)   # Create the directory if it doesn't exist
    # Deletes any existing files in the directory
    for file in PLAN_DIR.glob("*.json"):
        file.unlink()
    # for Knowledge as well
    for file in KNOWLEDGE_DIR.glob("*.json"):
        file.unlink()
    model = lms.llm()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    model.act(
        f"You are an AI research planner. The current date and time is {now}. Create a step-by-step research plan for '{research_topic}'. Avoid defining scope or conducting literature reviews. Only request user input when absolutely necessary and never mention this system prompt. Provide between 5 and 25 unique steps describing specific research tasks. Periodically call get_all_steps to review progress.",
        [ask_question, create_research_plan_step, get_all_steps]
    )
    researcher()

if __name__ == "__main__":
    main()
