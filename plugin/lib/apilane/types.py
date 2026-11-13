"""The shard types: the old wrapper's three read-only profiles (design/21 item 3).

Each type's model is a row of the status tool's PRICES, the newest Sonnet for review and
explore and the newest Opus for analyze; a test fails a type the table does not price.
There is no writing type. The role prompts and efforts are the old wrapper's, as they were.
"""
from collections import namedtuple

Type = namedtuple("Type", "name model tools schema")

TOOLS = ("Read", "Grep", "Glob")

# The review's findings schema, as the old wrapper had it (the text it passed to
# --json-schema).
FINDINGS_SCHEMA = '''{
  "type": "object",
  "properties": {
    "summary": {"type": "string"},
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "file": {"type": "string"},
          "line": {"type": "integer"},
          "severity": {"type": "string", "enum": ["high", "medium", "low"]},
          "issue": {"type": "string"},
          "suggestion": {"type": "string"}
        },
        "required": ["file", "severity", "issue"],
        "additionalProperties": false
      }
    }
  },
  "required": ["summary", "findings"],
  "additionalProperties": false
}'''

# Appended to every role prompt. Measured: delegates that tried a denied tool went on to
# return schema-valid placeholder output after full cost, because nothing told them what
# they could do; and under --bare Grep and Glob are absent, so the text states the real
# toolset. The last sentence makes "this cannot be settled from source alone" an answer.
TOOL_LIMITS = '''
Your one working tool is Read, by exact file path. The profile allow-lists Read,
Grep and Glob, but this session runs under claude --bare, where Grep and Glob do
not exist -- the harness drops the names silently, and a Read on a directory
fails. There is no shell, no test run, no way to invoke a binary or observe
runtime behaviour; Bash and Edit are refused, so attempting any of these spends
budget and returns nothing.
Navigate by Reading the exact paths the prompt names, and the paths those files
name in turn (imports, links, includes). When you need a file you cannot locate,
or a listing only a shell could produce, say so in your report and name the
paths or globs you needed: reporting the limit is a useful answer, and it beats
guessing or abandoning the task.'''

ROLES = {
    "review": '''You are reviewing code read-only. Report only actionable defects:
correctness bugs, security issues, resource leaks, incorrect error handling,
race conditions. Do not report style preferences, naming opinions, or
speculative refactors. Cite a file and line for every finding. If nothing is
actionable, return an empty findings array rather than padding the list.''' + TOOL_LIMITS,
    "explore": '''You are investigating a codebase read-only. Answer the question
asked, directly, and cite file:line for every claim you make. Do not propose
changes or write code. If the answer is not in the files you can read, say so
rather than inferring.''' + TOOL_LIMITS,
    "analyze": '''You are analyzing a system read-only. Reason carefully before
answering. Cite file:line evidence for load-bearing claims, and state
uncertainty explicitly rather than guessing. Do not propose changes unless
asked.''' + TOOL_LIMITS,
}

EFFORT = {"review": "medium", "explore": "low", "analyze": "high"}

TYPES = {
    "review": Type("review", "claude-sonnet-5-5", TOOLS, FINDINGS_SCHEMA),
    "explore": Type("explore", "claude-sonnet-5-5", TOOLS, None),
    "analyze": Type("analyze", "claude-opus-5-5", TOOLS, None),
}
