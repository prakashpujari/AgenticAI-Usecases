import puppeteer from 'puppeteer';
import { mkdirSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCREENSHOTS_DIR = join(__dirname, '..', 'docs', 'screenshots');
const BASE_URL = 'http://localhost:3000';

if (!existsSync(SCREENSHOTS_DIR)) {
  mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

const MOCK_RESULT = {
  dashboard: {
    application: 'calculator-api',
    runtime: '4.9',
    coverage: 87,
    testsExecuted: 24,
    testsPassed: 22,
    testsFailed: 2,
    passRate: 92,
    securityScore: 88,
    performanceScore: 81,
    confidenceScore: 85,
    riskScore: 18,
    productionReadiness: 84,
    recommendation: 'CONDITIONAL',
  },
  agent_reports: [
    {
      agent: 'api_design',
      score: 90,
      summary: 'The RAML specification is well-structured with clear endpoint definitions and proper HTTP method usage. Minor improvements recommended for response schemas.',
      findings: [
        { severity: 'low', title: 'Missing 404 response definition', detail: 'The /divide endpoint does not define a 404 response schema.', recommendation: 'Add a 404 response definition with an error schema to improve API documentation.' },
        { severity: 'info', title: 'Consider adding examples', detail: 'Adding request/response examples improves API discoverability.', recommendation: 'Add RAML examples for each endpoint.' },
      ],
      raw_llm_output: null,
    },
    {
      agent: 'mule_review',
      score: 85,
      summary: 'Mule flow configuration follows best practices. Error handling is present but could be more granular for production readiness.',
      findings: [
        { severity: 'medium', title: 'Generic error handler in divide flow', detail: 'The divide operation uses a catch-all error handler rather than specific error types.', recommendation: 'Use specific error handlers for EXPRESSION and DIVIDE_BY_ZERO error types.' },
      ],
      raw_llm_output: null,
    },
    {
      agent: 'munit',
      score: 87,
      summary: '22 of 24 MUnit tests passed with 87% code coverage. Two tests for edge cases are failing.',
      findings: [
        { severity: 'medium', title: 'test-divide-by-zero failing', detail: 'The divide-by-zero test case throws an unexpected exception type.', recommendation: 'Update error handling in the divide flow to return HTTP 400 with a proper message.' },
        { severity: 'low', title: 'test-large-numbers missing assertions', detail: 'Large number test case lacks precision assertions.', recommendation: 'Add precision validation for results exceeding 10^15.' },
      ],
      raw_llm_output: null,
    },
    {
      agent: 'security',
      score: 88,
      summary: 'Security posture is good. API authentication is configured correctly. One medium-severity issue found with input validation.',
      findings: [
        { severity: 'medium', title: 'No rate limiting configured', detail: 'The API policy does not include rate limiting, making it vulnerable to abuse.', recommendation: 'Apply a rate-limiting policy of 100 requests per minute per client.' },
        { severity: 'info', title: 'Consider adding CORS policy', detail: 'CORS policy is not explicitly configured.', recommendation: 'Add an explicit CORS policy to control cross-origin access.' },
      ],
      raw_llm_output: null,
    },
    {
      agent: 'performance',
      score: 81,
      summary: 'Performance is acceptable for a calculator API. Response times are within SLA. Caching could improve throughput for repeated calculations.',
      findings: [
        { severity: 'low', title: 'No caching for repeated operations', detail: 'Identical calculation requests are not cached.', recommendation: 'Implement a simple in-memory cache for idempotent operations.' },
      ],
      raw_llm_output: null,
    },
    {
      agent: 'executive_reporting',
      score: 85,
      summary: 'The calculator-api demonstrates solid overall quality. Address the 2 failing MUnit tests and rate limiting before promoting to production.',
      findings: [],
      raw_llm_output: null,
    },
  ],
  executive_summary: 'The calculator-api (Mule Runtime 4.9) has been evaluated by 6 AI agents across design, implementation, testing, security, and performance dimensions. Overall confidence score is 85/100 with a CONDITIONAL recommendation. The API is structurally sound with 87% test coverage and 22/24 passing tests. Key action items: fix the 2 failing MUnit edge-case tests, add rate limiting to the security policy, and refine error handling in the divide flow. These improvements will qualify the API for APPROVED production deployment.',
  artifacts: {
    munit_total: 24,
    munit_failures: 2,
    munit_coverage: 87,
  },
};

async function run() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  console.log('Navigating to dashboard...');
  await page.goto(BASE_URL, { waitUntil: 'networkidle2', timeout: 30000 });

  // Screenshot 1 — empty dashboard
  const shot1 = join(SCREENSHOTS_DIR, '01-dashboard-empty.png');
  await page.screenshot({ path: shot1, fullPage: false });
  console.log(`Saved: ${shot1}`);

  // Inject mock result via window.__injectMockResult
  console.log('Injecting mock result data...');
  const injected = await page.evaluate((data) => {
    if (typeof window.__injectMockResult === 'function') {
      window.__injectMockResult(data);
      return true;
    }
    return false;
  }, MOCK_RESULT);

  if (!injected) {
    console.log('__injectMockResult not available, filling form and clicking button...');
    // Fallback: click the Run Validation button and wait
    await page.click('button');
    try {
      await page.waitForFunction(
        () => document.body.innerText.includes('CONDITIONAL') || document.body.innerText.includes('APPROVED') || document.body.innerText.includes('BLOCKED'),
        { timeout: 180000 }
      );
    } catch (e) {
      console.log('Timeout waiting for result banner — taking screenshot anyway');
    }
  } else {
    // Wait for React to re-render with injected data
    await new Promise(r => setTimeout(r, 1000));
    await page.waitForFunction(
      () => document.body.innerText.includes('CONDITIONAL') || document.body.innerText.includes('APPROVED') || document.body.innerText.includes('BLOCKED'),
      { timeout: 10000 }
    );
  }

  // Screenshot 2 — results dashboard
  const shot2 = join(SCREENSHOTS_DIR, '02-dashboard-results.png');
  await page.screenshot({ path: shot2, fullPage: true });
  console.log(`Saved: ${shot2}`);

  // Click the first agent card to expand it
  console.log('Expanding first agent card...');
  try {
    // Find first agent card button and click it
    const agentButtons = await page.$$('button');
    // The first button is "Run Validation", agent card buttons come after
    // We want the second button (first agent card)
    if (agentButtons.length > 1) {
      await agentButtons[1].click();
      await new Promise(r => setTimeout(r, 600));
    }
  } catch (e) {
    console.log('Could not click agent card:', e.message);
  }

  // Screenshot 3 — agent findings expanded
  const shot3 = join(SCREENSHOTS_DIR, '03-agent-findings.png');
  await page.screenshot({ path: shot3, fullPage: true });
  console.log(`Saved: ${shot3}`);

  await browser.close();
  console.log('Done! All screenshots saved to', SCREENSHOTS_DIR);
}

run().catch(e => {
  console.error('Screenshot script error:', e);
  process.exit(1);
});
