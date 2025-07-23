# AI Research Assistant

This project is a Python-based AI research assistant that automates the process of researching a given topic. It uses a large language model (LLM) to create a research plan, execute it by searching the web and crawling websites, and finally generates a detailed report based on the gathered information.

## How it Works

The assistant is designed to work with a local LLM server provided by [LM Studio](https://lmstudio.ai/).

1.  **Planning Phase:** The user provides a research topic. The AI planner (`main.py`) interacts with the LLM to generate a step-by-step research plan.
2.  **Execution Phase:** Another AI agent (`researcher` function in `main.py`) executes the plan. It uses tools like DuckDuckGo search and a web crawler to find and extract information.
3.  **Knowledge Storage:** Relevant information found during the research is stored locally in the `research_knowledge` directory.
4.  **Reporting Phase:** Once all research steps are completed, the assistant compiles the gathered knowledge into a markdown report in the `reports` directory.

## Getting Started

### Prerequisites

*   Python 3.x
*   [LM Studio](https://lmstudio.ai/) installed and running with a loaded model.
*   The local LM Studio server must be running.

### Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd searchassistant
    ```
2.  Create a virtual environment and activate it:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
    ```
3.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Usage

Run the main script from the project's root directory:

```bash
python main.py
```

The script will first prompt you for a research topic. It will then proceed with the planning and execution phases.

### Model Recommendations

For optimal performance, it is recommended to use the following models in LM Studio:

*   **Lucy-128k:** A good starting point for most research tasks. Use at maximum context length.
*   **Qwen3-32b:** For more complex research that requires a larger context window and more powerful reasoning capabilities. Use at maximum context length if resources are available.

It is recommended to set the context length to the maximum supported by the model for best results.

## Project Structure

```
.
├── .gitignore         # Specifies files and directories to be ignored by Git
├── LICENSE            # Project license
├── main.py            # The main script to run the research assistant
├── requirements.txt   # Project dependencies
└── README.md          # This file
```

**Note:** The following directories are generated at runtime and are not tracked by Git (as specified in `.gitignore`):

*   `research_plans/`: Stores the generated research plans.
*   `research_knowledge/`: Stores the knowledge gathered during research.
*   `reports/`: Stores the final markdown reports.
*   `.venv/`: The Python virtual environment directory.
