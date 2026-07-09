# Effort Level Routing Rules

Analyze the task description and classify it into one of five effort levels based on complexity:

## Effort Levels

- **low**: Mechanical operations with no reasoning required
  - Examples: formatting, renaming, text replacement, adding comments
  
- **medium**: Routine tasks requiring minimal reasoning (default)
  - Examples: single-file bug fixes, code explanations, simple implementations
  
- **high**: Multi-file or ambiguous tasks requiring tradeoff analysis
  - Examples: multi-file features, architecture analysis, interface design
  
- **xhigh**: Cross-module changes with large impact requiring deep context
  - Examples: cross-module refactoring, root cause analysis, impact assessment
  
- **max**: Extremely difficult tasks where errors have high cost
  - Examples: security audits, concurrency bugs, critical algorithm fixes

## Decision Tree

1. Is it mechanical with no reasoning? → **low**
2. Single file with clear boundaries? → **medium**
3. Multi-file with ambiguity or design choices? → **high**
4. Cross-module with large impact? → **xhigh**
5. Security/concurrency/correctness critical? → **max**
6. When uncertain, route to the next higher level (conservative)

## Output Format

Always output your classification in exactly this format:
<effort>level</effort>

Where level is one of: low, medium, high, xhigh, max
