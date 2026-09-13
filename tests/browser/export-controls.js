export async function openExports(page) {
  const toggle = page.getByRole('button', {name:'Export', exact:true});
  if (await toggle.isVisible() && await toggle.getAttribute('aria-expanded') !== 'true') await toggle.click();
}
