#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

import * as XLSX from "xlsx";

const DATA_SHEET_NAME = "题目列表";

function normalizeText(value) {
  if (value == null) {
    return "";
  }
  return String(value).trim();
}

function parseArgs(argv) {
  const options = {
    workbook: "",
    limit: 0,
    previewAll: false,
  };

  let index = 0;
  while (index < argv.length) {
    const key = argv[index];
    if (key === "--preview-all") {
      options.previewAll = true;
      index += 1;
      continue;
    }
    const value = argv[index + 1];
    if (!key?.startsWith("--")) {
      throw new Error(`不支持的参数：${key || ""}`);
    }
    if (value == null || value.startsWith("--")) {
      throw new Error(`参数 ${key} 缺少取值`);
    }
    switch (key) {
      case "--workbook":
        options.workbook = path.resolve(value);
        break;
      case "--limit":
        options.limit = Number(value);
        if (!Number.isFinite(options.limit) || options.limit <= 0) {
          throw new Error("--limit 必须是正整数");
        }
        break;
      default:
        throw new Error(`不支持的参数：${key}`);
    }
    index += 2;
  }

  if (!options.workbook) {
    throw new Error("缺少 --workbook");
  }
  return options;
}

function detectOptionCount(headerRow) {
  let count = 0;
  for (const cell of headerRow) {
    const matched = normalizeText(cell).match(/^选项(\d+)$/);
    if (!matched) {
      continue;
    }
    count = Math.max(count, Number(matched[1]));
  }
  return count;
}

function toQuestionRecord(headerRow, row, rowNumber) {
  const record = {};
  headerRow.forEach((header, index) => {
    record[normalizeText(header)] = normalizeText(row[index]);
  });

  const options = [];
  const optionCount = detectOptionCount(headerRow);
  for (let index = 1; index <= optionCount; index += 1) {
    const label = normalizeText(record[`选项${index}`]);
    const labelEn = normalizeText(record[`英文选项${index}`]);
    if (!label && !labelEn) {
      continue;
    }
    options.push({
      label,
      labelEn,
    });
  }

  return {
    rowNumber,
    title: normalizeText(record["题目"]),
    titleEn: normalizeText(record["英文题目"]),
    category: normalizeText(record["分类"]),
    sourceUrl: normalizeText(record["问题来源地址"]),
    deadlineAt: normalizeText(record["截止时间"]),
    announceAt: normalizeText(record["开奖时间"]),
    scheduledPublishAt: normalizeText(record["定时发布时间"]),
    candidateQuestionId: normalizeText(record["候选题ID"]) || normalizeText(record["候选题id"]),
    imageFileName: normalizeText(record["图片文件名"]),
    options,
  };
}

function isNonEmptyRow(row) {
  return row.some((value) => normalizeText(value));
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (!fs.existsSync(options.workbook)) {
    throw new Error(`未找到 workbook：${options.workbook}`);
  }

  const workbook = XLSX.read(fs.readFileSync(options.workbook), { type: "buffer" });
  const dataSheet = workbook.Sheets[DATA_SHEET_NAME];
  if (!dataSheet) {
    throw new Error(`未找到 sheet：${DATA_SHEET_NAME}`);
  }

  const rows = XLSX.utils.sheet_to_json(dataSheet, {
    header: 1,
    defval: "",
    raw: false,
  });
  const headerRow = Array.isArray(rows[0]) ? rows[0] : [];
  const dataRows = rows
    .slice(1)
    .map((row, index) => ({ row, rowNumber: index + 2 }))
    .filter(({ row }) => Array.isArray(row) && isNonEmptyRow(row));

  const visibleRows = options.previewAll
    ? dataRows
    : dataRows.slice(0, options.limit || 10);

  console.log(
    JSON.stringify(
      {
        status: "ok",
        workbook: options.workbook,
        totalRows: dataRows.length,
        returnedRows: visibleRows.length,
        previewAll: options.previewAll,
        limit: options.previewAll ? 0 : (options.limit || 10),
        rows: visibleRows.map(({ row, rowNumber }) => toQuestionRecord(headerRow, row, rowNumber)),
      },
      null,
      2,
    ),
  );
}

try {
  main();
} catch (error) {
  console.error(
    JSON.stringify(
      {
        status: "error",
        message: error instanceof Error ? error.message : String(error),
      },
      null,
      2,
    ),
  );
  process.exit(1);
}
