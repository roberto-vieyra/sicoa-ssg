import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";

test("flujo real: acceso, 962 filas, captura, acuse, accesibilidad y descargas", async ({
  page,
}, testInfo) => {
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    if (
      /^https?:/.test(request.url()) &&
      new URL(request.url()).hostname !==
        new URL(testInfo.project.use.baseURL!).hostname
    )
      externalRequests.push(request.url());
  });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.evaluate(() => document.fonts.ready);
  await expect(
    page.getByRole("heading", { name: "Bienvenido a SICOA-SSG" }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByLabel("Usuario", { exact: true }).fill("admin");
  await page.getByLabel("Contraseña", { exact: true }).fill("SicoaSSG2026!");
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(
    page.getByRole("heading", { name: "Control de correspondencia" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "SSG962", exact: true }),
  ).toBeVisible();
  const initialCount = Number(
    await page.locator(".kpi > strong").first().innerText(),
  );
  expect(initialCount).toBeGreaterThanOrEqual(962);
  await expect(page.getByRole("table")).toContainText("DG-0366-26");
  await page.evaluate(() => document.fonts.ready);
  const geometry = await page.evaluate(() => ({
    width: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    height: document.documentElement.clientHeight,
    scrollHeight: document.documentElement.scrollHeight,
    secureContext: window.isSecureContext,
  }));
  await testInfo.attach("geometry.json", {
    body: JSON.stringify(geometry),
    contentType: "application/json",
  });
  if (process.env.E2E_LAN_IP && !process.env.E2E_LAN_IP.startsWith("127."))
    expect(geometry.secureContext).toBe(false);
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width);
  if (testInfo.project.name === "desktop")
    expect(geometry.scrollHeight).toBeLessThanOrEqual(geometry.height);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("consola.png"),
    fullPage: true,
  });

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Abrir menú de operación" }).click();
    await page
      .getByRole("dialog", { name: "Menú de operación" })
      .getByRole("button", { name: "Directorio" })
      .click();
    const directory = page.getByRole("dialog", { name: /Directorio/i });
    await expect(directory).toBeVisible();
    await directory.getByRole("button", { name: "Cerrar ventana" }).click();
  }
  await page.getByRole("button", { name: "Nuevo oficio", exact: true }).click();
  const form = page.getByRole("dialog", { name: "Nuevo oficio" });
  await expect(form).toBeVisible();
  const folio = (
    await form.locator(".capture-banner strong").innerText()
  ).trim();
  expect(folio).toMatch(/^SSG\d{3,4}$/);
  if (initialCount === 962) expect(folio).toBe("SSG963");
  await form
    .getByLabel("Número de oficio", { exact: true })
    .fill(`PRUEBA-E2E-${testInfo.project.name}/2026`);
  await form.getByRole("button", { name: "3d", exact: true }).click();
  await expect(form).toContainText("EN TIEMPO");
  await form
    .getByRole("button", { name: "+ Agregar co-destinatario", exact: true })
    .click();
  await form
    .getByLabel("Co-destinatario 1", { exact: true })
    .fill("DESTINATARIO DE PRUEBA LAN");
  await form
    .getByLabel("Firmante", { exact: true })
    .fill("ARQ. MARTHA MARGARITA REYNÉS NOGUERA");
  await expect(form.getByLabel("Cargo del firmante")).toHaveValue(
    "SUBDIRECTORA DE SERVICIOS GENERALES",
  );
  await form
    .getByLabel("Asunto", { exact: true })
    .fill(`Verificación de captura por excepción ${testInfo.project.name}`);
  await form.getByLabel("Área responsable").selectOption("GAI");
  await form.getByLabel("Responsable / analista").fill("PATY GAI");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await form.screenshot({ path: testInfo.outputPath("captura.png") });
  await form
    .getByRole("button", { name: "Registrar oficio", exact: true })
    .click();
  await expect(form).not.toBeVisible();
  await page.getByRole("button", { name: folio, exact: true }).click();
  const original = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Volante de turno", exact: true })
    .click();
  const sample = testInfo.outputPath("documento-de-prueba.pdf");
  await (await original).saveAs(sample);
  await page
    .getByRole("button", {
      name: "Registrar atención / Subir acuse",
      exact: true,
    })
    .click();
  const attention = page.getByRole("dialog", {
    name: "Registrar atención / Subir acuse",
  });
  await attention
    .getByLabel("Nota de atención")
    .fill("Prueba E2E completada con acuse de recepción.");
  await attention
    .getByLabel("Número de oficio de respuesta")
    .fill("SSG/RESPUESTA/2026");
  await attention.getByLabel("Acuse de respuesta · PDF").setInputFiles(sample);
  await attention
    .getByRole("button", { name: "Guardar atención y acuse" })
    .click();
  await expect(attention).not.toBeVisible();
  await expect(page.locator(".inspector .badge")).toHaveText("ATENDIDO");
  await expect(page.locator(".inspector .version")).toHaveText("V2");
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Volante de turno", exact: true })
    .click();
  const pdf = await downloadPromise;
  await pdf.saveAs(testInfo.outputPath("volante.pdf"));
  expect(
    readFileSync(testInfo.outputPath("volante.pdf")).subarray(0, 5).toString(),
  ).toBe("%PDF-");
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Cerrar inspector" }).click();
  await page
    .getByRole("checkbox", { name: `Marcar ${folio} para entrega` })
    .check();
  await page.getByRole("button", { name: /^Entrega\s*\(1\)$/ }).click();
  for (const [name, filename] of [
    ["Semáforo ejecutivo y alertas", "alertas.pdf"],
    ["Hoja de entrega física", "entrega.pdf"],
  ]) {
    const pending = page.waitForEvent("download");
    await page.getByRole("button", { name: new RegExp(name) }).click();
    await (await pending).saveAs(testInfo.outputPath(filename));
    expect(
      readFileSync(testInfo.outputPath(filename)).subarray(0, 5).toString(),
    ).toBe("%PDF-");
  }
  expect(externalRequests).toEqual([]);
  expect(errors).toEqual([]);
});
