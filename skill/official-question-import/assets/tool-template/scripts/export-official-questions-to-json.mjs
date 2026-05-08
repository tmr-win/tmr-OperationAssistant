#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

import * as XLSX from "xlsx";

const DATA_SHEET_NAME = "题目列表";
const DEFAULT_VALUE_SHEET_NAME = "默认值";

const DEFAULT_KEYS = [
  ["默认分类", "category"],
  ["默认来源地址", "sourceUrl"],
  ["默认开奖时间", "announceAt"],
  ["默认定时发布时间", "scheduledPublishAt"],
];

function normalizeText(value) {
  if (value == null) {
    return "";
  }
  return String(value).trim();
}

function parseArgs(argv) {
  const options = {
    workbook: "",
    outputJsonFile: "",
  };

  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
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
      case "--output-json-file":
        options.outputJsonFile = path.resolve(value);
        break;
      default:
        throw new Error(`不支持的参数：${key}`);
    }
  }

  if (!options.workbook) {
    throw new Error("缺少 --workbook");
  }
  return options;
}

function detectOptionCountFromHeader(headerRow) {
  let maxOptionCount = 0;
  for (const cell of headerRow) {
    const matched = normalizeText(cell).match(/^选项(\d+)$/);
    if (!matched) {
      continue;
    }
    maxOptionCount = Math.max(maxOptionCount, Number(matched[1]));
  }
  return maxOptionCount;
}

function isNonEmptyRow(row) {
  return row.some((value) => normalizeText(value));
}

function parseQuestionFromExistingRow(headerRow, row) {
  const record = {};
  headerRow.forEach((header, index) => {
    record[normalizeText(header)] = normalizeText(row[index]);
  });

  const existingOptionCount = detectOptionCountFromHeader(headerRow);
  const options = [];
  for (let index = 1; index <= existingOptionCount; index += 1) {
    const label = normalizeText(record[`选项${index}`]);
    const labelEn = normalizeText(record[`英文选项${index}`]);
    if (!label && !labelEn) {
      continue;
    }
    options.push({ label, labelEn });
  }

  const yesLabel = options[0]?.label || "";
  const noLabel = options[1]?.label || "";

  return {
    title: normalizeText(record["题目"]),
    titleEn: normalizeText(record["英文题目"]),
    rawResolutionRule: "",
    yesLabel,
    noLabel,
    resolutionRuleNote: "",
    needsRuleReview: false,
    labelReason: "",
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

function parseDefaults(defaultSheet) {
  if (!defaultSheet) {
    return {};
  }

  const rows = XLSX.utils.sheet_to_json(defaultSheet, {
    header: 1,
    defval: "",
    raw: false,
  });
  const defaults = {};
  const labelMap = new Map(DEFAULT_KEYS);
  for (const row of rows.slice(1)) {
    if (!Array.isArray(row)) {
      continue;
    }
    const label = normalizeText(row[0]);
    const value = normalizeText(row[1]);
    const key = labelMap.get(label);
    if (key && value) {
      defaults[key] = value;
    }
  }
  return defaults;
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
  const dataRows = rows.slice(1).filter((row) => Array.isArray(row) && isNonEmptyRow(row));
  const questions = dataRows.map((row) => parseQuestionFromExistingRow(headerRow, row));
  const defaults = parseDefaults(workbook.Sheets[DEFAULT_VALUE_SHEET_NAME]);

  const payload = { questions };
  if (Object.keys(defaults).length > 0) {
    payload.defaults = defaults;
  }

  if (options.outputJsonFile) {
    fs.writeFileSync(options.outputJsonFile, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
  }

  console.log(
    JSON.stringify(
      {
        status: "ok",
        workbook: options.workbook,
        outputJsonFile: options.outputJsonFile,
        questionCount: questions.length,
        payload,
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
