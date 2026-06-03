"""Knowledge base: structured analysis of the user's solved submissions.

This package turns raw accepted submissions into reusable knowledge: the
pattern/technique used, a generalized code template, the user's coding-style
traits, and bridges between a new problem and problems already solved.

The analysis itself runs offline (``leetmind analyze-solutions``) so chat-time
stays cheap: the agent only reads precomputed, sanitized rows.
"""

# Bump when the analysis prompt/schema changes meaningfully so that
# `analyze-solutions` knows to re-analyze previously processed submissions.
ANALYSIS_VERSION = 1
