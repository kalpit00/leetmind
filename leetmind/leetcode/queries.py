"""GraphQL query strings for the LeetCode API.

LeetCode's GraphQL schema is undocumented and changes over time. These queries
reflect the schema as of writing; if a query starts returning ``errors`` or
``null``, this is the first place to update. Operation names matter and must
match the ``operationName`` sent in the request body.
"""

# Paginated list of all problems with metadata + the authenticated user's status.
PROBLEMSET_QUESTION_LIST = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList: questionList(
    categorySlug: $categorySlug
    limit: $limit
    skip: $skip
    filters: $filters
  ) {
    total: totalNum
    questions: data {
      frontendQuestionId: questionFrontendId
      title
      titleSlug
      difficulty
      paidOnly: isPaidOnly
      status
      topicTags {
        name
        slug
      }
    }
  }
}
"""

# The authenticated user's created favorite lists (private lists).
MY_FAVORITE_LISTS = """
query myCreatedFavoriteList {
  myCreatedFavoriteList {
    favorites {
      name
      slug
      isPublicFavorite
    }
  }
}
"""

# Questions inside one favorite list (paginated).
FAVORITE_QUESTION_LIST = """
query favoriteQuestionList($favoriteSlug: String!, $limit: Int, $skip: Int, $version: String = "v2") {
  favoriteQuestionList(
    favoriteSlug: $favoriteSlug
    limit: $limit
    skip: $skip
    version: $version
  ) {
    questions {
      titleSlug
      title
      questionFrontendId
    }
    totalLength
    hasMore
  }
}
"""

# Per-problem submission history for the authenticated user.
SUBMISSION_LIST = """
query submissionList($offset: Int!, $limit: Int!, $lastKey: String, $questionSlug: String!) {
  questionSubmissionList(
    offset: $offset
    limit: $limit
    lastKey: $lastKey
    questionSlug: $questionSlug
  ) {
    lastKey
    hasNext
    submissions {
      id
      title
      titleSlug
      statusDisplay
      lang
      langName
      runtime
      memory
      timestamp
      hasNotes
      notes
    }
  }
}
"""

# Full details (including code) for one submission.
SUBMISSION_DETAILS = """
query submissionDetails($submissionId: Int!) {
  submissionDetails(submissionId: $submissionId) {
    code
    timestamp
    statusCode
    runtimeDisplay
    memoryDisplay
    notes
    lang {
      name
      verboseName
    }
    question {
      questionId
      title
      titleSlug
    }
  }
}
"""

# Lightweight identity check that the session cookie is valid.
WHOAMI = """
query globalData {
  userStatus {
    isSignedIn
    username
  }
}
"""
