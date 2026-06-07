/**
 * AIOps Platform - Automated Screenshot Capture Script
 * Uses Puppeteer to capture 25 high-quality screenshots of the UI
 *
 * Usage: node capture-screenshots.js
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const SCREENSHOTS_DIR = path.join(__dirname, 'docs', 'screenshots');
const BASE_URL = 'http://localhost:5173';
const API_URL = 'http://localhost:8000';

// Create screenshots directory if it doesn't exist
if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

// Screenshot configurations
const screenshots = [
  // Group 1: Dashboard (5)
  {
    name: '01_dashboard_full_page',
    url: `${BASE_URL}`,
    wait: 3000,
    fullPage: true,
    description: 'Full dashboard view'
  },
  {
    name: '02_dashboard_kpi_cards',
    url: `${BASE_URL}`,
    wait: 2000,
    clip: { x: 0, y: 0, width: 1280, height: 200 },
    description: 'Dashboard KPI cards'
  },
  {
    name: '03_dashboard_filters',
    url: `${BASE_URL}`,
    wait: 2000,
    selector: '[class*="filter"]',
    description: 'Filter bar with dropdowns'
  },
  {
    name: '04_incidents_table_header',
    url: `${BASE_URL}`,
    wait: 2000,
    selector: 'table thead',
    description: 'Incidents table header'
  },
  {
    name: '05_incidents_table_full',
    url: `${BASE_URL}`,
    wait: 2000,
    selector: 'table',
    description: 'Full incidents table with data'
  },

  // Group 2: Incident Details (6)
  {
    name: '06_incident_details_header',
    url: `${BASE_URL}/incidents/INCIDENT_ID`,
    wait: 3000,
    clip: { x: 0, y: 0, width: 1280, height: 150 },
    description: 'Incident header with title and severity'
  },
  {
    name: '07_incident_details_info_grid',
    url: `${BASE_URL}/incidents/INCIDENT_ID`,
    wait: 3000,
    selector: '[class*="info"], [class*="grid"]',
    description: 'Incident information grid'
  },
  {
    name: '08_incident_details_overview_tab',
    url: `${BASE_URL}/incidents/INCIDENT_ID`,
    wait: 3000,
    fullPage: true,
    description: 'Incident overview tab content'
  },
  {
    name: '09_incident_details_rca_tab',
    url: `${BASE_URL}/incidents/INCIDENT_ID`,
    wait: 3000,
    fullPage: true,
    description: 'Incident RCA tab content'
  },
  {
    name: '10_incident_details_evidence_tab',
    url: `${BASE_URL}/incidents/INCIDENT_ID`,
    wait: 3000,
    fullPage: true,
    description: 'Incident evidence tab'
  },
  {
    name: '11_incident_details_action_buttons',
    url: `${BASE_URL}/incidents/INCIDENT_ID`,
    wait: 2000,
    clip: { x: 0, y: 100, width: 1280, height: 100 },
    description: 'Incident action buttons'
  },

  // Group 3: Remediation (5)
  {
    name: '12_remediation_header_risk',
    url: `${BASE_URL}/remediation/INCIDENT_ID`,
    wait: 3000,
    clip: { x: 0, y: 0, width: 1280, height: 200 },
    description: 'Remediation header and risk assessment'
  },
  {
    name: '13_remediation_actions_list_1',
    url: `${BASE_URL}/remediation/INCIDENT_ID`,
    wait: 3000,
    selector: '[class*="action"]',
    description: 'First remediation action card'
  },
  {
    name: '14_remediation_actions_list_2',
    url: `${BASE_URL}/remediation/INCIDENT_ID`,
    wait: 3000,
    fullPage: true,
    description: 'Multiple remediation actions'
  },
  {
    name: '15_remediation_success_criteria',
    url: `${BASE_URL}/remediation/INCIDENT_ID`,
    wait: 3000,
    selector: '[class*="criteria"], [class*="success"]',
    description: 'Success criteria checklist'
  },
  {
    name: '16_remediation_approval_form',
    url: `${BASE_URL}/remediation/INCIDENT_ID`,
    wait: 3000,
    selector: 'form, textarea, button',
    description: 'Remediation approval form'
  },

  // Group 4: Metrics (4)
  {
    name: '17_metrics_kpi_cards',
    url: `${BASE_URL}/metrics`,
    wait: 3000,
    clip: { x: 0, y: 0, width: 1280, height: 200 },
    description: 'Metrics KPI cards'
  },
  {
    name: '18_metrics_timeline_chart',
    url: `${BASE_URL}/metrics`,
    wait: 3000,
    selector: '[class*="chart"]',
    description: 'Timeline chart'
  },
  {
    name: '19_metrics_mttd_mttr_chart',
    url: `${BASE_URL}/metrics`,
    wait: 3000,
    selector: 'svg',
    description: 'MTTD vs MTTR chart'
  },
  {
    name: '20_metrics_severity_breakdown',
    url: `${BASE_URL}/metrics`,
    wait: 3000,
    fullPage: true,
    description: 'Severity breakdown'
  },

  // Group 5: API Documentation (3)
  {
    name: '21_api_swagger_overview',
    url: `${API_URL}/docs`,
    wait: 3000,
    fullPage: true,
    description: 'Swagger API documentation'
  },
  {
    name: '22_api_swagger_post_incident',
    url: `${API_URL}/docs`,
    wait: 3000,
    selector: '[id*="post"]',
    description: 'POST incident endpoint'
  },
  {
    name: '23_api_swagger_response',
    url: `${API_URL}/docs`,
    wait: 3000,
    fullPage: true,
    description: 'API response schema'
  }
];

let browser;
let incidentId = null;

async function createTestIncident() {
  /**
   * Create a test incident via API
   */
  try {
    console.log('📝 Creating test incident...');
    const response = await fetch(`${API_URL}/api/v1/incidents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'Database Connection Pool Exhaustion',
        description: 'PostgreSQL connection pool at 95% utilization causing API timeouts',
        severity: 'P2_HIGH',
        affected_services: ['api-server', 'database', 'cache'],
        affected_components: ['postgresql', 'connection_pool'],
        environment: 'production',
        detection_source: 'prometheus',
        confidence_score: 0.92,
        business_impact: 'Payment processing delayed for 500+ customers',
        customer_impact: 500
      })
    });

    const data = await response.json();
    incidentId = data.id;
    console.log(`✅ Test incident created: ${incidentId}\n`);

    // Run RCA
    await fetch(`${API_URL}/api/v1/incidents/${incidentId}/rca`, {
      method: 'POST'
    });

    // Generate remediation
    await fetch(`${API_URL}/api/v1/incidents/${incidentId}/remediation`, {
      method: 'POST'
    });

    return incidentId;
  } catch (error) {
    console.error('❌ Failed to create test incident:', error.message);
    throw error;
  }
}

async function captureScreenshot(page, config) {
  /**
   * Capture a single screenshot
   */
  const filename = path.join(SCREENSHOTS_DIR, `${config.name}.png`);

  // Replace placeholder with actual incident ID
  let url = config.url;
  if (incidentId && url.includes('INCIDENT_ID')) {
    url = url.replace('INCIDENT_ID', incidentId);
  }

  // Skip if we still have placeholders
  if (url.includes('INCIDENT_ID')) {
    console.log(`⏭️  Skipping ${config.name} - No incident data available`);
    return;
  }

  try {
    console.log(`📸 Capturing: ${config.name}`);
    console.log(`   URL: ${url}`);
    console.log(`   Description: ${config.description}`);

    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
    await page.waitForTimeout(config.wait || 2000);

    // Click through tabs if needed
    if (config.selector && config.selector.includes('tab')) {
      const tabs = await page.$$(config.selector);
      if (tabs.length > 1) {
        await tabs[1].click(); // Click second tab
        await page.waitForTimeout(1000);
      }
    }

    const options = {
      path: filename,
      type: 'png',
      quality: 95
    };

    if (config.fullPage) {
      options.fullPage = true;
    } else if (config.clip) {
      options.clip = config.clip;
    } else if (config.selector) {
      const element = await page.$(config.selector);
      if (element) {
        const boundingBox = await element.boundingBox();
        if (boundingBox) {
          options.clip = boundingBox;
        }
      }
    }

    await page.screenshot(options);
    console.log(`   ✅ Saved to: ${filename}\n`);
    return filename;
  } catch (error) {
    console.error(`   ❌ Failed: ${error.message}\n`);
  }
}

async function main() {
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║     AIOps Platform - Automated Screenshot Capture             ║');
  console.log('║                                                                ║');
  console.log('║  This script will capture 25 screenshots of your UI            ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');

  try {
    // Verify services are running
    console.log('🔍 Verifying services...');
    try {
      const response = await fetch(`${API_URL}/health`);
      if (response.status !== 200) throw new Error('API not healthy');
      console.log('✅ Backend API is running\n');
    } catch (error) {
      throw new Error(`Backend API not available at ${API_URL}`);
    }

    // Create test incident
    console.log('📋 Setting up test data...\n');
    await createTestIncident();

    // Launch browser
    console.log('🌐 Launching browser...\n');
    browser = await puppeteer.launch({
      headless: false,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 720 });

    // Capture all screenshots
    console.log('📸 Capturing screenshots...\n');
    const capturedFiles = [];

    for (const config of screenshots) {
      const file = await captureScreenshot(page, config);
      if (file) {
        capturedFiles.push(file);
      }
    }

    // Summary
    console.log('╔════════════════════════════════════════════════════════════════╗');
    console.log('║                 ✅ Capture Complete!                           ║');
    console.log('╚════════════════════════════════════════════════════════════════╝\n');

    console.log(`📊 Summary:`);
    console.log(`   Total captured: ${capturedFiles.length}`);
    console.log(`   Output directory: ${SCREENSHOTS_DIR}\n`);

    console.log(`📋 Screenshots captured:`);
    console.log(`   Group 1: Dashboard (5)`);
    console.log(`   Group 2: Incident Details (6)`);
    console.log(`   Group 3: Remediation (5)`);
    console.log(`   Group 4: Metrics (4)`);
    console.log(`   Group 5: API Documentation (3)\n`);

    console.log(`📁 View screenshots at:`);
    console.log(`   ${SCREENSHOTS_DIR}\n`);

    console.log(`📚 Next steps:`);
    console.log(`   1. Review screenshots in docs/screenshots/`);
    console.log(`   2. Update documentation with screenshot references`);
    console.log(`   3. Commit and push to GitHub\n`);

    await browser.close();
  } catch (error) {
    console.error('\n❌ Error:', error.message);
    if (browser) {
      await browser.close();
    }
    process.exit(1);
  }
}

// Run the script
main();
