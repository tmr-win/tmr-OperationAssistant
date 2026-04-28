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
    jsonFile: "",
    mode: "replace",
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
      case "--json-file":
        options.jsonFile = path.resolve(value);
        break;
      case "--mode":
        options.mode = value;
        break;
      default:
        throw new Error(`不支持的参数：${key}`);
    }
  }

  if (!options.workbook) {
    throw new Error("缺少 --workbook");
  }
  if (!options.jsonFile) {
    throw new Error("缺少 --json-file");
  }
  if (!["replace", "append"].includes(options.mode)) {
    throw new Error("--mode 仅支持 replace 或 append");
  }

  return options;
}

function readPayload(jsonFile) {
  const content = fs.readFileSync(jsonFile, "utf-8");
  const payload = JSON.parse(content);
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("JSON 顶层必须是对象");
  }
  if (!Array.isArray(payload.questions) || payload.questions.length === 0) {
    throw new Error("questions 必须是非空数组");
  }
  return payload;
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

function buildHeader(optionCount) {
  const header = ["题目", "英文题目", "分类", "问题来源地址"];
  for (let index = 1; index <= optionCount; index += 1) {
    header.push(`选项${index}`, `英文选项${index}`);
  }
  header.push("截止时间", "开奖时间", "定时发布时间", "候选题ID", "图片文件名");
  return header;
}

function buildQuestionRow(question, optionCount) {
  const options = Array.isArray(question.options) ? question.options : [];
  const row = [
    normalizeText(question.title),
    normalizeText(question.titleEn),
    normalizeText(question.category),
    normalizeText(question.sourceUrl),
  ];

  for (let index = 0; index < optionCount; index += 1) {
    const option = options[index] || {};
    row.push(normalizeText(option.label), normalizeText(option.labelEn));
  }

  row.push(
    normalizeText(question.deadlineAt),
    normalizeText(question.announceAt),
    normalizeText(question.scheduledPublishAt),
    normalizeText(question.candidateQuestionId),
    normalizeText(question.imageFileName || question.imageFile),
  );
  return row;
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

  return {
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

function buildDefaultSheetRows(defaults, shouldClearValues) {
  const rows = [["字段", "值"]];
  for (const [label, key] of DEFAULT_KEYS) {
    rows.push([label, normalizeText(defaults?.[key])]);
  }
  if (!shouldClearValues && !defaults) {
    rows.push(["", ""]);
  }
  return rows;
}

function ensureSheet(workbook, sheetName, rows) {
  workbook.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(rows);
  if (!workbook.SheetNames.includes(sheetName)) {
    workbook.SheetNames.push(sheetName);
  }
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (!fs.existsSync(options.workbook)) {
    throw new Error(`未找到 workbook：${options.workbook}`);
  }

  const payload = readPayload(options.jsonFile);
  const workbook = XLSX.read(fs.readFileSync(options.workbook), { type: "buffer" });
  const existingDataSheet = workbook.Sheets[DATA_SHEET_NAME];
  if (!existingDataSheet) {
    throw new Error(`未找到 sheet：${DATA_SHEET_NAME}`);
  }

  const existingRows = XLSX.utils.sheet_to_json(existingDataSheet, {
    header: 1,
    defval: "",
    raw: false,
  });
  const existingHeader = Array.isArray(existingRows[0]) ? existingRows[0] : [];
  const existingDataRows = existingRows.slice(1).filter((row) => Array.isArray(row) && isNonEmptyRow(row));

  const incomingOptionCount = Math.max(
    ...payload.questions.map((question) => (Array.isArray(question.options) ? question.options.length : 0)),
    2,
  );
  const existingOptionCount = detectOptionCountFromHeader(existingHeader);
  const maxOptionCount = Math.max(incomingOptionCount, existingOptionCount || 2);

  const nextRows = [buildHeader(maxOptionCount)];
  if (options.mode === "append") {
    existingDataRows.forEach((row) => {
      nextRows.push(
        buildQuestionRow(
          parseQuestionFromExistingRow(existingHeader, row),
          maxOptionCount,
        ),
      );
    });
  }
  payload.questions.forEach((question) => {
    nextRows.push(buildQuestionRow(question, maxOptionCount));
  });
  ensureSheet(workbook, DATA_SHEET_NAME, nextRows);

  const shouldRewriteDefaults = Boolean(payload.defaults) || options.mode === "replace";
  if (shouldRewriteDefaults) {
    ensureSheet(
      workbook,
      DEFAULT_VALUE_SHEET_NAME,
      buildDefaultSheetRows(payload.defaults || null, options.mode === "replace"),
    );
  }

  const workbookBuffer = XLSX.write(workbook, {
    type: "buffer",
    bookType: "xlsx",
  });
  fs.writeFileSync(options.workbook, workbookBuffer);

  console.log(
    JSON.stringify(
      {
        status: "ok",
        workbook: options.workbook,
        mode: options.mode,
        questionCount: payload.questions.length,
        optionColumnCount: maxOptionCount,
        defaultsWritten: shouldRewriteDefaults,
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
