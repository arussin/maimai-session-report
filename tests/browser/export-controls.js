export async function openExports(page) {
  await page.locator('.toolbar').waitFor({state:'visible'});
  const toggle = page.getByRole('button', {name:'Export', exact:true});
  if (await toggle.isVisible() && await toggle.getAttribute('aria-expanded') !== 'true') await toggle.click();
}
