# Avathon API Integration Plan

## Phase 1: Authentication & Documentation Scraping
1. **Create authenticated scraping script** that:
   - Uses AVATHON_USERNAME and AVATHON_PASSWORD from .env
   - Handles login flow: `https://renewables.apm.avathon.com` → `/auth` → docs
   - Maintains session cookies for authenticated requests
   - Implements robust retry logic and error handling

2. **Build comprehensive endpoint discovery** using:
   - BeautifulSoup to parse HTML structure
   - Selenium WebDriver if needed for JavaScript-heavy pages
   - Recursive crawling to find all API endpoint documentation pages
   - Extract endpoint details: URL patterns, methods, parameters, responses

3. **Generate structured API specification**:
   - Create JSON schema similar to existing `pharos_swagger.json` pattern
   - Include all endpoints, parameters, authentication requirements
   - Document request/response formats and validation rules

**Phase 1 Completion:**
- `git add .`, `git commit`, `git push`
- Post DART-227 Slack thread update about scraping completion and API spec generation

## Phase 2: PydanticAI Toolset Integration
4. **Create Avathon toolset following existing patterns**:
   - Structure: `src/tools/avathon/` (similar to pharos/procore)
   - Files: `client.py`, `toolset.py`, `utils/`, `specs/avathon_api.json`
   - Follow exact same architecture as `PharosToolset` class

5. **Implement client authentication**:
   - Handle username/password login flow
   - Manage session tokens and refresh logic  
   - Support both planning and execution contexts

6. **Build dynamic tool generation**:
   - Auto-generate PydanticAI tools from scraped API spec
   - Handle parameter validation and type conversion
   - Implement comprehensive error handling and retries

**Phase 2 Completion:**
- `git add .`, `git commit`, `git push`
- Post DART-227 Slack thread update about toolset creation and PydanticAI integration

## Phase 3: Integration & Testing  
7. **Register with orchestrators**:
   - Add to `safe_discovery.py` BUNDLED_APPS
   - Update `builtin_toolsets.py` for tool availability
   - Ensure compatibility with ExecutionJoule orchestrator

8. **Create comprehensive test suite**:
   - Test authentication flow
   - Validate endpoint discovery completeness
   - Test tool execution with real API calls
   - Performance and reliability testing

**Phase 3 Completion:**
- `git add .`, `git commit`, `git push`
- Post DART-227 Slack thread update about full integration completion and testing results

## Key Technical Decisions
- **Authentication**: Session-based login using credentials from .env
- **Scraping Strategy**: Authenticated crawling with comprehensive endpoint detection  
- **Architecture**: Follow exact PharosToolset pattern for consistency
- **Integration**: Full PydanticAI toolset with dependency injection
- **Error Handling**: Robust retry logic and informative error messages