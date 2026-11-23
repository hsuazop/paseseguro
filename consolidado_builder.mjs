import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const baseDir = "C:/dev/django/proyectos/paseseguro";
const outputDir = `${baseDir}/outputs/consolidado_villa_olimpica`;
const data = JSON.parse(await fs.readFile(`${baseDir}/consolidado_data.json`, "utf8"));
await fs.mkdir(outputDir, { recursive: true });

const wb = Workbook.create();
const summary = wb.worksheets.add("Resumen");
const master = wb.worksheets.add("Registro consolidado");
const payments = wb.worksheets.add("Pagos detalle");
const review = wb.worksheets.add("Revisión coincidencias");
const sources = wb.worksheets.add("Fuentes y método");

const font = "Arial";
const navy = "#1F4E78";
const blue = "#D9EAF7";
const light = "#F4F7FA";
const amber = "#FFF2CC";
const red = "#FCE4D6";
const green = "#E2F0D9";
const border = "#D9E2F3";

function fmtPhone(v) {
  const s = String(v || "").replace(/\D/g, "");
  return s.length === 8 ? `${s.slice(0,4)}-${s.slice(4)}` : s;
}
function addTable(sheet, range, name) {
  const t = sheet.tables.add(range, true, name);
  t.style = "TableStyleMedium2";
  t.showFilterButton = true;
  return t;
}
function styleHeader(sheet, range) {
  const r = sheet.getRange(range);
  r.format = { fill: navy, font: { name: font, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
  r.format.borders = { preset: "all", style: "thin", color: "#FFFFFF" };
}
function styleBody(sheet, range) {
  const r = sheet.getRange(range);
  r.format.font = { name: font, size: 10, color: "#1F2937" };
  r.format.verticalAlignment = "center";
}

// Summary output
summary.showGridLines = false;
summary.tabColor = navy;
summary.getRange("A1:H1").merge();
summary.getRange("A1").values = [["Consolidado de personas y pagos de vigilancia 2026"]];
summary.getRange("A1:H1").format = { font: { name: font, size: 15, bold: true, color: navy }, verticalAlignment: "center" };
summary.getRange("A2:H2").merge();
summary.getRange("A2").values = [["Villa Olímpica, Sector 1. El celular se usa como identificador principal; los casos ambiguos se mantienen para revisión."]];
summary.getRange("A2:H2").format = { font: { name: font, size: 10, italic: true, color: "#5B6573" }, wrapText: true };
summary.getRange("A4:B9").values = [
  ["Indicador", "Valor"],
  ["Filas de origen procesadas", data.summary.raw_records],
  ["Personas/registros consolidados", data.summary.clusters],
  ["Con celular", data.summary.clusters_with_phone],
  ["Sin celular", data.summary.clusters_without_phone],
  ["Casos con conflicto por celular", data.summary.conflicts],
];
summary.getRange("D4:E7").values = [
  ["Indicador de pagos", "Valor"],
  ["Movimientos de pago analizados", data.summary.payment_rows],
  ["Registros con pagos acumulados", data.records.filter(x => Number(x.pagos_registrados) > 0).length],
  ["Total pagado registrado", data.records.reduce((a,x)=>a+Number(x.pago_total_2026||0),0)],
];
styleHeader(summary, "A4:B4"); styleHeader(summary, "D4:E4");
styleBody(summary, "A5:B9"); styleBody(summary, "D5:E7");
summary.getRange("B5:B9").format.numberFormat = "#,##0";
summary.getRange("E5:E6").format.numberFormat = "#,##0";
summary.getRange("E7").format.numberFormat = "#,##0.00";
summary.getRange("A11:H11").merge();
summary.getRange("A11").values = [["Cómo usar el consolidado"]];
summary.getRange("A11:H11").format = { fill: blue, font: { name: font, size: 11, bold: true, color: navy } };
summary.getRange("A12:H15").values = [
  ["1", "Use Registro consolidado como base para registrar personas en el sistema.", null, null, null, null, null, null],
  ["2", "El campo celular es el identificador principal cuando existe.", null, null, null, null, null, null],
  ["3", "Revise Revisión coincidencias antes de fusionar o corregir registros.", null, null, null, null, null, null],
  ["4", "Pagos detalle conserva los movimientos mensuales usados para el acumulado.", null, null, null, null, null, null],
];
summary.getRange("A12:H15").format = { font: { name: font, size: 10 }, wrapText: true, verticalAlignment: "center" };
summary.getRange("A12:A15").format.font = { name: font, size: 10, bold: true, color: navy };
for (let r = 12; r <= 15; r++) summary.mergeCells(`B${r}:H${r}`);
summary.getRange("B12:H15").format.wrapText = false;
summary.getRange("A1:H15").format.autofitColumns();
summary.getRange("A:A").format.columnWidth = 28;
summary.getRange("B:B").format.columnWidth = 18;
summary.getRange("C:C").format.columnWidth = 3;
summary.getRange("D:D").format.columnWidth = 28;
summary.getRange("E:E").format.columnWidth = 18;
summary.getRange("F:H").format.columnWidth = 16;
summary.getRange("A1:H15").format.autofitRows();

// Main registry
master.showGridLines = false;
master.tabColor = "#5B9BD5";
master.getRange("A1:V1").merge();
master.getRange("A1").values = [["Registro consolidado para alta en el sistema"]];
master.getRange("A1:V1").format = { font: { name: font, size: 14, bold: true, color: navy } };
master.getRange("A2:V2").merge();
master.getRange("A2").values = [["Una fila por persona o registro consolidado. Los teléfonos están normalizados a 8 dígitos y se muestran como ####-####."]];
master.getRange("A2:V2").format = { font: { name: font, size: 10, italic: true, color: "#5B6573" }, wrapText: true };
const masterHeaders = ["ID registro","Nombre canónico","Celular","Celulares detectados","Nombres detectados","Sector","Bloque","Casa","Clave catastral","Vehículo","Placa","Observaciones","Fuentes","Estado consolidación","Registros origen","Total pagado 2026","Pagos registrados","Meses con pago"];
const masterRows = data.records.map(x => [x.id,x.nombre_canonico,fmtPhone(x.celular),String(x.celulares_detectados||"").split(" | ").filter(Boolean).map(fmtPhone).join(" | "),x.nombres_detectados,x.sector,x.bloque,x.casa,x.clave_catastral,x.vehiculo,x.placa,x.observaciones,x.fuentes,x.estado_consolidacion,x.registros_origen,Number(x.pago_total_2026||0),Number(x.pagos_registrados||0),x.meses_con_pago]);
master.getRangeByIndexes(3,0,masterRows.length+1,masterHeaders.length).values = [masterHeaders,...masterRows];
styleHeader(master, `A4:R4`); styleBody(master, `A5:R${masterRows.length+4}`);
master.getRange(`O5:O${masterRows.length+4}`).format.numberFormat = "#,##0";
master.getRange(`P5:P${masterRows.length+4}`).format.numberFormat = "#,##0.00";
master.getRange(`Q5:Q${masterRows.length+4}`).format.numberFormat = "#,##0";
master.getRange(`A4:R${masterRows.length+4}`).format.borders = { insideHorizontal: { style: "thin", color: border }, bottom: { style: "thin", color: border } };
addTable(master, `A4:R${masterRows.length+4}`, "RegistroConsolidado");
master.getRange(`N5:N${masterRows.length+4}`).conditionalFormats.add("containsText", { text: "CONFLICTO", format: { fill: red, font: { bold: true, color: "#9C0006" } } });
master.getRange(`N5:N${masterRows.length+4}`).conditionalFormats.add("containsText", { text: "REVISAR", format: { fill: amber, font: { bold: true, color: "#7F6000" } } });
master.getRange(`C5:D${masterRows.length+4}`).format.numberFormat = "@";
master.freezePanes.freezeRows(4);
master.freezePanes.freezeColumns(2);
master.getRange("A:R").format.columnWidth = 15;
master.getRange("A:A").format.columnWidth = 12; master.getRange("B:B").format.columnWidth = 28; master.getRange("C:D").format.columnWidth = 16; master.getRange("E:E").format.columnWidth = 32; master.getRange("I:I").format.columnWidth = 18; master.getRange("J:J").format.columnWidth = 24; master.getRange("K:K").format.columnWidth = 16; master.getRange("L:M").format.columnWidth = 28; master.getRange("N:N").format.columnWidth = 28; master.getRange("R:R").format.columnWidth = 32;

// Payment detail
payments.showGridLines = false;
payments.tabColor = "#70AD47";
payments.getRange("A1:F1").merge(); payments.getRange("A1").values = [["Detalle de pagos de vigilancia analizados"]];
payments.getRange("A1:F1").format = { font: { name: font, size: 14, bold: true, color: navy } };
payments.getRange("A2:F2").merge(); payments.getRange("A2").values = [["Se usaron las hojas mensuales de enero a octubre de 2026. El total del registro consolidado se calculó por coincidencia normalizada de nombre."]];
payments.getRange("A2:F2").format = { font: { name: font, size: 10, italic: true, color: "#5B6573" }, wrapText: true };
const pHeaders = ["Hoja mes","Fila origen","Nombre reportado","Nombre normalizado","Monto","Concepto"];
const pRows = data.payment_detail.map(x => [x.sheet,x.row,x.name,x.name_norm,Number(x.amount||0),x.concept]);
payments.getRangeByIndexes(3,0,pRows.length+1,pHeaders.length).values = [pHeaders,...pRows];
styleHeader(payments, `A4:F4`); styleBody(payments, `A5:F${pRows.length+4}`);
payments.getRange(`E5:E${pRows.length+4}`).format.numberFormat = "#,##0.00";
addTable(payments, `A4:F${pRows.length+4}`, "PagosDetalle");
payments.freezePanes.freezeRows(4); payments.getRange("A:F").format.columnWidth = 18; payments.getRange("C:C").format.columnWidth = 30; payments.getRange("D:D").format.columnWidth = 32; payments.getRange("F:F").format.columnWidth = 20;

// Review sheet
review.showGridLines = false;
review.tabColor = "#ED7D31";
review.getRange("A1:H1").merge(); review.getRange("A1").values = [["Revisión de coincidencias y conflictos"]];
review.getRange("A1:H1").format = { font: { name: font, size: 14, bold: true, color: navy } };
review.getRange("A2:H2").merge(); review.getRange("A2").values = [["No se fusionaron automáticamente los nombres parecidos con celulares distintos. Confirme estos casos antes de corregir la base."]];
review.getRange("A2:H2").format = { font: { name: font, size: 10, italic: true, color: "#5B6573" }, wrapText: true };
const cHeaders = ["ID registro","Tipo de revisión","Celulares","Nombres","Acción sugerida"];
const cRows = data.conflicts.map(x => [x.registro,x.tipo,x.celulares,x.nombres,"Verificar fuente y decidir si se conserva un solo registro"]);
const fRows = data.fuzzy.map(x => [x.registro1,"Coincidencia de nombre aproximada",`${fmtPhone(x.celular1)} vs ${fmtPhone(x.celular2)}`,`${x.nombre1} vs ${x.nombre2}`,`${x.accion} (${x.similitud})`]);
review.getRangeByIndexes(3,0,cRows.length+fRows.length+1,cHeaders.length).values = [cHeaders,...cRows,...fRows];
styleHeader(review, `A4:E4`); styleBody(review, `A5:E${cRows.length+fRows.length+4}`);
addTable(review, `A4:E${cRows.length+fRows.length+4}`, "Revisiones");
review.getRange(`B5:B${cRows.length+fRows.length+4}`).conditionalFormats.add("containsText", { text: "aproximada", format: { fill: amber, font: { bold: true, color: "#7F6000" } } });
review.getRange(`B5:B${cRows.length+fRows.length+4}`).conditionalFormats.add("containsText", { text: "celular", format: { fill: red, font: { bold: true, color: "#9C0006" } } });
review.freezePanes.freezeRows(4); review.getRange("A:A").format.columnWidth = 14; review.getRange("B:B").format.columnWidth = 32; review.getRange("C:C").format.columnWidth = 24; review.getRange("D:D").format.columnWidth = 48; review.getRange("E:E").format.columnWidth = 58;

// Sources and method
sources.showGridLines = false;
sources.tabColor = "#A5A5A5";
sources.getRange("A1:D1").merge(); sources.getRange("A1").values = [["Fuentes y método de consolidación"]];
sources.getRange("A1:D1").format = { font: { name: font, size: 14, bold: true, color: navy } };
sources.getRange("A3:C3").values = [["Fuente procesada","Filas incorporadas","Uso"]]; styleHeader(sources,"A3:C3");
const srcRows = Object.entries(data.summary.source_counts).map(([k,v]) => [k,Number(v),k.includes("PAGOS")?"Identificación y validación de pagos":"Datos de persona, ubicación o vehículo"]);
sources.getRangeByIndexes(3,0,srcRows.length,3).values = srcRows; styleBody(sources,`A4:C${srcRows.length+3}`); addTable(sources,`A3:C${srcRows.length+3}`,"Fuentes");
const methodStart = srcRows.length + 6;
sources.getRange(`A${methodStart}:D${methodStart}`).merge(); sources.getRange(`A${methodStart}`).values = [["Reglas aplicadas"]]; sources.getRange(`A${methodStart}:D${methodStart}`).format = { fill: blue, font: { name: font, size: 11, bold: true, color: navy } };
sources.getRange(`A${methodStart+1}:D${methodStart+5}`).values = [
  ["Identificador principal","Celular normalizado a los últimos 8 dígitos. Se muestra como ####-####.",null,null],
  ["Coincidencia automática","Se consolidaron filas que comparten exactamente el mismo celular.",null,null],
  ["Nombre sin celular","Se agruparon coincidencias exactas de nombre solo cuando no había celular para distinguirlas.",null,null],
  ["Nombre parecido","Se marcaron para revisión las similitudes altas con celulares distintos.",null,null],
  ["Pagos","Se sumaron los movimientos de las hojas mensuales de enero a octubre 2026 por nombre normalizado.",null,null],
];
sources.getRange(`A${methodStart+1}:D${methodStart+5}`).format = { font: { name: font, size: 10 }, wrapText: true, verticalAlignment: "center" };
sources.getRange(`A${methodStart+1}:A${methodStart+5}`).format.font = { name: font, size: 10, bold: true, color: navy };
sources.getRange("A:D").format.columnWidth = 26; sources.getRange("B:B").format.columnWidth = 18; sources.getRange("C:C").format.columnWidth = 45; sources.getRange("D:D").format.columnWidth = 18;

wb.recalculate();
const errorScan = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
console.log(errorScan.ndjson);
const check = await wb.inspect({ kind: "table", range: `Registro consolidado!A4:R12`, include: "values,formulas", tableMaxRows: 9, tableMaxCols: 18 });
console.log(check.ndjson);
for (const sheetName of ["Resumen","Registro consolidado","Revisión coincidencias"]) {
  const preview = await wb.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${outputDir}/${sheetName.replaceAll(" ","_")}.png`, new Uint8Array(await preview.arrayBuffer()));
}
const out = await SpreadsheetFile.exportXlsx(wb);
await out.save(`${outputDir}/Consolidado_personas_vigilancia_2026.xlsx`);
console.log(`SAVED ${outputDir}/Consolidado_personas_vigilancia_2026.xlsx`);
