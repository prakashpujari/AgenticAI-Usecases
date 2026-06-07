const puppeteer = require('puppeteer');
const fs = require('fs');

(async () => {
  let browser;
  try {
    console.log('Launching browser...');
    browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();

    // Capture console messages
    const consoleLogs = [];
    page.on('console', msg => {
      consoleLogs.push({
        type: msg.type(),
        text: msg.text(),
        location: msg.location()
      });
    });

    // Capture errors
    const errors = [];
    page.on('error', err => errors.push(err));
    page.on('pageerror', err => errors.push(err));

    console.log('Loading page http://localhost:5174/...');
    try {
      await page.goto('http://localhost:5174/', { waitUntil: 'networkidle2', timeout: 10000 });
    } catch (e) {
      console.log('Navigation timeout or error (page may still be loaded)');
    }

    await page.waitForTimeout(2000);

    // Get page content
    const content = await page.content();
    const bodyText = await page.evaluate(() => document.body.innerText);

    console.log('\n=== PAGE CONTENT ===');
    console.log('Body text length:', bodyText.length);
    console.log('Body text preview:', bodyText.substring(0, 500));

    console.log('\n=== CONSOLE OUTPUT ===');
    console.log('Total messages:', consoleLogs.length);
    consoleLogs.forEach(log => {
      console.log(`[${log.type}] ${log.text}`);
    });

    console.log('\n=== ERRORS ===');
    if (errors.length === 0) {
      console.log('No errors');
    } else {
      errors.forEach(err => console.log(err.toString()));
    }

    // Check for specific elements
    const hasRoot = await page.evaluate(() => !!document.getElementById('root'));
    const hasScript = await page.evaluate(() => document.querySelectorAll('script').length);
    const title = await page.title();

    console.log('\n=== PAGE ANALYSIS ===');
    console.log('Title:', title);
    console.log('Has root element:', hasRoot);
    console.log('Script tags:', hasScript);

    // Try to get all text content
    const allText = await page.evaluate(() => {
      return {
        innerHTML: document.body.innerHTML.substring(0, 1000),
        innerText: document.body.innerText.substring(0, 1000),
        childCount: document.body.children.length
      };
    });

    console.log('\n=== HTML CONTENT ===');
    console.log('Inner HTML preview:', allText.innerHTML);
    console.log('Inner text preview:', allText.innerText);
    console.log('Child elements:', allText.childCount);

    // Screenshot
    await page.screenshot({ path: 'page-screenshot.png' });
    console.log('\n✅ Screenshot saved to page-screenshot.png');

    await browser.close();
  } catch (error) {
    console.error('Error:', error.message);
    if (browser) await browser.close();
    process.exit(1);
  }
})();
