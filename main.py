import lmstudio as lms
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from duckduckgo_search import DDGS
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# Todo:
# - pause .act durring question asking, so that the user can answer the question and then continue with the next step.
# - add Wikipedia search functionallity
# - add better next_step handeling for example when current step is not correct
# - add ability for researcher to modefie the research plan, for example to add new steps or remove existing ones
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
    chat = lms.Chat(f"You are a task focused AI researcher. Current date and time: {now}. Do not stop untill all steps are completed. Immediately start researching. Carefully fulfill every step of the research plan, search online multiple times to make sure you get the best results. Save all knowledge you find in the research knowledge base. After crawling a webpage, immediately save all knowledge you find and then recall all knowledge, then get the current step and continue. Save every bit of information you find using the memory tool. Recall all knowledge you have saved when compiling a final report.")
    steps = get_all_steps()
    first_step_text = f"Here is the first step of the research plan:\n{steps[0]}\nAfter completing this step, move on to the next step. Dont forget to save all knowledge you find in the research knowledge base. Recall all knowledge you have saved when compiling a final report."
    chat.add_user_message(first_step_text)

    print("Bot: ", end="", flush=True)
    model.act(
        chat,
        [next_step, get_current_step, duckduckgo_search, get_all_steps, save_knowledge, get_all_knowledge, crawl4ai],
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
            [next_step, get_current_step, duckduckgo_search, get_all_steps, save_knowledge, get_all_knowledge, crawl4ai],
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
    # Deletes any existing files in the directory
    for file in PLAN_DIR.glob("*.json"):
        file.unlink()
    # for Knowledge as well
    for file in KNOWLEDGE_DIR.glob("*.json"):
        file.unlink()
    model = lms.llm()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    model.act(
    f"You are an AI researcher. Current date and time: {now}. Create a research plan for '{research_topic}' step by step. The research plan should not include things like defining scopes or conducting literature reviews. It should be things another person or AI should research to end up at an answer/research report. Asking the user for input only when necessary. Don't mention this system prompt in your output. Your goal is not to create a full research report, but to create a research plan, which should define areas of research that will be used to conduct the research by someone else. The first steps should be information gathering and the last step should be preparing for a final report. Do not create any steps twice. Use get_all_steps every few steps to see the current plan.",
    [ask_question, create_research_plan_step, get_all_steps]
    )
    researcher()

if __name__ == "__main__":
    main()