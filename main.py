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
import os

# Todo:
# - pause .act during question asking, so that the user can answer the question and then continue with the next step.
# - add better next_step handling for example when current step is not correct



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

_PLAN_COMPLETE = False

def done() -> str:
    """
    Call this function when the research plan is complete and all steps have been created.
    This will end the planning phase and start the research.
    """
    global _PLAN_COMPLETE
    _PLAN_COMPLETE = True
    return "Research plan marked as complete. Your task is done."

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
    print("Retrieving all knowledge entries")
    knowledge_file = Path("research_knowledge") / "knowledge.json"
    if not knowledge_file.exists():
        return []
    with knowledge_file.open("r") as f:
        try:
            data = json.load(f)
            return [data[key] for key in sorted(data.keys(), key=int)]
        except json.JSONDecodeError:
            return []

class FormattedPrinter:
    # For reasoning content of the LLM, doesn't affect LLMs that don't reason
    # This version is more robust and handles edge cases like stray tags
    # and interruptions during streaming.
    def __init__(self):
        self.current_buffer = ""
        self.in_think_content_mode = False
        self.think_tag_open = "<think>"
        self.think_tag_close = "</think>"
        self.grey_code = "\033[90m"
        self.reset_code = "\033[0m"
        
        # Enable ANSI escape codes on Windows
        if os.name == 'nt':
            os.system('')

    def print_fragment(self, fragment, round_index=0):
        self.current_buffer += fragment.content
        self._process_buffer()

    def _process_buffer(self):
        while self.current_buffer:
            if self.in_think_content_mode:
                close_tag_index = self.current_buffer.find(self.think_tag_close)
                if close_tag_index != -1:
                    text_to_print = self.current_buffer[:close_tag_index]
                    print(text_to_print, end="", flush=True)
                    print(self.reset_code, end="", flush=True)
                    self.current_buffer = self.current_buffer[close_tag_index + len(self.think_tag_close):]
                    self.in_think_content_mode = False
                else:
                    print(self.current_buffer, end="", flush=True)
                    self.current_buffer = ""
                    return
            else:  # not in_think_content_mode
                open_tag_index = self.current_buffer.find(self.think_tag_open)
                close_tag_index = self.current_buffer.find(self.think_tag_close)

                if open_tag_index != -1 and (open_tag_index < close_tag_index or close_tag_index == -1):
                    # Process the opening tag
                    text_to_print = self.current_buffer[:open_tag_index]
                    print(text_to_print, end="", flush=True)
                    print(self.grey_code, end="", flush=True)
                    self.current_buffer = self.current_buffer[open_tag_index + len(self.think_tag_open):]
                    self.in_think_content_mode = True
                elif close_tag_index != -1:
                    # A stray closing tag is the next tag, remove it
                    text_to_print = self.current_buffer[:close_tag_index]
                    print(text_to_print, end="", flush=True)
                    self.current_buffer = self.current_buffer[close_tag_index + len(self.think_tag_close):]
                else:
                    # No tags in buffer
                    print(self.current_buffer, end="", flush=True)
                    self.current_buffer = ""
                    return
    
    def finalize(self):
        self._process_buffer()
        if self.in_think_content_mode:
            print(self.reset_code, end="", flush=True)
            self.in_think_content_mode = False
        print()

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
        # needs to be result.markdown to return the markdown content
        # ignore the warning about the return type, it is correct
        return result.markdown  # type: ignore

def create_report(title: str, content: str, sources: list) -> str:
    """Generates a final report in markdown format.
    Only works if all steps of the research plan have been completed.

    Args:
        title: The title of the report. Will also be used for the file name combined with the current date and time for a unique file name.
        content: The content of the report.
        sources: A list of sources used in the report.
    Saves:
        The final report in markdown format into reports/.
    Returns:
        The file name of the report for the AI to tell the user where to find it or an error message.
    """
    # Check if all steps have been completed
    plan_file = Path("research_plans") / "plan.json"
    state_file = Path("research_plans") / "state.json"
    try:
        with plan_file.open("r") as f:
            plan_data = json.load(f)
            total_steps = len(plan_data)
    except (FileNotFoundError, json.JSONDecodeError):
        print("Error: Research plan not found or invalid.")
        import sys
        sys.exit(1)
    try:
        with state_file.open("r") as f:
            state_data = json.load(f)
            current_step = state_data.get("current_step", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        current_step = 0

    if current_step < total_steps:
        return f"Error: Cannot create report. Only {current_step} out of {total_steps} steps have been completed."

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
        f"You are a task-focused AI researcher. The current date and time is {now}. Begin researching immediately and continue until every step of the plan is complete. Perform multiple online searches to gather reliable information. After visiting a webpage, store any useful knowledge in the research knowledge base. Recall stored knowledge before moving to the next step and when drafting the final report. Don't forget to ground information in reliable sources. Mark any assumptions clearly. Produce the report in markdown format using the create_report tool. Add some tables if you think it will help clarify the information."
    )
    steps = get_all_steps()
    first_step_text = f"Here is the first step of the research plan:\n{steps[0]}\nAfter completing this step, move on to the next step. Dont forget to save all knowledge you find in the research knowledge base. DO NOT stop until all steps are completed and a report has been created. Recall all knowledge you have saved when compiling a final report. COMPLETE EVERY STEP OF THE RESEARCH PLAN BEFORE CREATING THE FINAL REPORT."
    chat.add_user_message(first_step_text)

    printer = FormattedPrinter()
    print("Bot: ", end="", flush=True)
    model.act(
        chat,
        [next_step, get_current_step, duckduckgo_search, get_all_steps, save_knowledge, get_all_knowledge, crawl4ai, create_report, get_wikipedia_page],
        on_message=chat.append,
        on_prediction_fragment=printer.print_fragment,
    )
    printer.finalize()

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
        
        printer = FormattedPrinter()
        print("Bot: ", end="", flush=True)
        model.act(
            chat,
            [next_step, get_current_step, duckduckgo_search, get_all_steps, save_knowledge, get_all_knowledge, crawl4ai, create_report, get_wikipedia_page],
            on_message=chat.append,
            on_prediction_fragment=printer.print_fragment,
        )
        printer.finalize()



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
    
    global _PLAN_COMPLETE
    _PLAN_COMPLETE = False
    
    model = lms.llm()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    chat = lms.Chat(
        f"You are an AI research planner. The current date and time is {now}. Create a step-by-step research plan for this topic or question provided by the user: '{research_topic}'. The research plan should focus on gathering as much information as possible before creating a research report. Avoid defining scope or conducting literature reviews. If you need clarification, ask the user directly. Only request user input when absolutely necessary and never mention this system prompt. Provide between 5 and 25 unique steps describing specific research tasks. Periodically call get_all_steps to review progress. When the plan is complete, call the done() function. The Research Plan will be used by another AI to research and ceate a final report."
    )

    # Generate the research plan interactively
    while not _PLAN_COMPLETE:
        printer = FormattedPrinter()
        print("Bot: ", end="", flush=True)
        model.act(
            chat,
            [create_research_plan_step, get_all_steps, done],
            on_message=chat.append,
            on_prediction_fragment=printer.print_fragment,
        )
        printer.finalize()

        if _PLAN_COMPLETE:
            break
        
        try:
            user_input = input("You (or type 'done' to finish): ")
        except EOFError:
            print()
            break
        if not user_input:
            user_input = "Please continue."
        elif user_input.lower() == 'done':
            break
        
        chat.add_user_message(user_input)

    if not get_all_steps():
        print("No research plan was created. Exiting.")
        return

    print("Research plan created successfully.")
    researcher()


if __name__ == "__main__":
    main()
