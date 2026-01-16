#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: "Comprehensive email verification and finder tool capable of handling 10K+ records with retry mechanisms, bulk finder, and production-ready features"

backend:
  - task: "Authentication System"
    implemented: true
    working: true
    file: "auth.py, server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "Auth system with register/login/JWT implemented and working"

  - task: "Single Email Verification"
    implemented: true
    working: true
    file: "email_verifier.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "SMTP + DNS + MX verification with provider detection working"

  - task: "Bulk Email Verification"
    implemented: true
    working: true
    file: "queue_manager.py, server.py, Verifier.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "partial"
        agent: "main"
        comment: "Bulk verification implemented but user reported 'failed to verify' issues. Needs better error handling and retry mechanism"
      - working: true
        agent: "main"
        comment: "Improved with CSV validation, better error handling, sample CSV downloads, comprehensive instructions, and retry count display"

  - task: "Single Email Finder"
    implemented: true
    working: true
    file: "email_finder.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "Pattern-based email finding with 10 patterns working"

  - task: "Bulk Email Finder"
    implemented: false
    working: "NA"
    file: "email_finder.py, queue_manager.py, server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "NOT IMPLEMENTED - User reported 'can't find Bulk Finder'. Need to add CSV upload for bulk email finding"

  - task: "Retry Mechanism"
    implemented: false
    working: "NA"
    file: "queue_manager.py, email_verifier.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "NOT IMPLEMENTED - User requested retry mechanism for failed verifications. Need automatic retry with configurable attempts"

  - task: "Proxy Support"
    implemented: "partial"
    working: "partial"
    file: "queue_manager.py, email_verifier.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "partial"
        agent: "main"
        comment: "Proxy CRUD endpoints exist but proxy rotation not implemented in verifier"

  - task: "Job Management (Pause/Resume/Stop)"
    implemented: true
    working: "partial"
    file: "queue_manager.py, server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "partial"
        agent: "main"
        comment: "Backend endpoints exist but no UI controls for pause/resume"

frontend:
  - task: "Single Email Verification UI"
    implemented: true
    working: true
    file: "pages/Verifier.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "Single verification UI working with real-time results"

  - task: "Bulk Email Verification UI"
    implemented: true
    working: "partial"
    file: "pages/Verifier.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "partial"
        agent: "main"
        comment: "Bulk verification UI exists but needs better error display and retry controls"

  - task: "Single Email Finder UI"
    implemented: true
    working: true
    file: "pages/Finder.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "Single finder UI working well"

  - task: "Bulk Email Finder UI"
    implemented: false
    working: "NA"
    file: "pages/Finder.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "NOT IMPLEMENTED - Need to add bulk CSV upload UI for finding multiple emails"

  - task: "Retry Controls UI"
    implemented: false
    working: "NA"
    file: "pages/Verifier.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "NOT IMPLEMENTED - Need UI to show retry status and manual retry button"

metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 0
  run_ui: false

test_plan:
  current_focus:
    - "Bulk Email Finder"
    - "Retry Mechanism"
    - "Error Handling Improvements"
  stuck_tasks:
    - "Bulk Email Verification (user reported failures)"
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: "Initial codebase analysis complete. Identified 3 critical missing features: 1) Bulk Email Finder, 2) Retry Mechanism, 3) Better error handling. Services are running. Ready to implement after user confirmation."