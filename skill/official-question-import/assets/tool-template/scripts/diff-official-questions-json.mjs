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

const QUESTION_FIELDS = [
  "title",
  "titleEn",
  "category",
  "sourceUrl",
  "deadlineAt",
  "announceAt",
  "scheduledPublishAt",
  "candidateQuestionId",
  "imageFileName",
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
    limit: 10,
    previewAll: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key?.startsWith("--")) {
      throw new Error(`不支持的参数：${key || ""}`);
    }
    if (key === "--preview-all") {
      options.previewAll = true;
      continue;
    }
    const value = argv[index + 1];
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
      case "--limit":
        options.limit = Number(value);
        if (!Number.isFinite(options.limit) || options.limit <= 0) {
          throw new Error("--limit 必须是正整数");
        }
        break;
      default:
        throw new Error(`不支持的参数：${key}`);
    }
    index += 1;
  }

  if (!options.workbook) {
    throw new Error("缺少 --workbook");
  }
  if (!options.jsonFile) {
    throw new Error("缺少 --json-file");
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

function exportCurrentPayload(workbookPath) {
  if (!fs.existsSync(workbookPath)) {
    throw new Error(`未找到 workbook：${workbookPath}`);
  }

  const workbook = XLSX.read(fs.readFileSync(workbookPath), { type: "buffer" });
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
  const questions = rows
    .slice(1)
    .filter((row) => Array.isArray(row) && isNonEmptyRow(row))
    .map((row) => parseQuestionFromExistingRow(headerRow, row));
  const defaults = parseDefaults(workbook.Sheets[DEFAULT_VALUE_SHEET_NAME]);
  const payload = { questions };
  if (Object.keys(defaults).length > 0) {
    payload.defaults = defaults;
  }
  return payload;
}

function loadCandidatePayload(jsonFile) {
  const payload = JSON.parse(fs.readFileSync(jsonFile, "utf-8"));
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("候选 JSON 顶层必须是对象");
  }
  if (!Array.isArray(payload.questions)) {
    throw new Error("候选 JSON 缺少 questions 数组");
  }
  return payload;
}

function diffDefaults(beforeDefaults = {}, afterDefaults = {}) {
  const changes = [];
  const keys = new Set([...Object.keys(beforeDefaults), ...Object.keys(afterDefaults)]);
  for (const key of keys) {
    const beforeValue = normalizeText(beforeDefaults[key]);
    const afterValue = normalizeText(afterDefaults[key]);
    if (beforeValue === afterValue) {
      continue;
    }
    changes.push({ field: key, before: beforeValue, after: afterValue });
  }
  return changes;
}

function normalizeOptions(options) {
  if (!Array.isArray(options)) {
    return [];
  }
  return options.map((option) => ({
    label: normalizeText(option?.label),
    labelEn: normalizeText(option?.labelEn),
  }));
}

function optionsEqual(beforeOptions, afterOptions) {
  if (beforeOptions.length !== afterOptions.length) {
    return false;
  }
  for (let index = 0; index < beforeOptions.length; index += 1) {
    if (beforeOptions[index].label !== afterOptions[index].label) {
      return false;
    }
    if (beforeOptions[index].labelEn !== afterOptions[index].labelEn) {
      return false;
    }
  }
  return true;
}

function diffQuestion(beforeQuestion, afterQuestion, rowIndex) {
  const fieldChanges = [];
  for (const field of QUESTION_FIELDS) {
    const beforeValue = normalizeText(beforeQuestion?.[field]);
    const afterValue = normalizeText(afterQuestion?.[field]);
    if (beforeValue === afterValue) {
      continue;
    }
    fieldChanges.push({ field, before: beforeValue, after: afterValue });
  }

  const beforeOptions = normalizeOptions(beforeQuestion?.options);
  const afterOptions = normalizeOptions(afterQuestion?.options);
  if (!optionsEqual(beforeOptions, afterOptions)) {
    fieldChanges.push({
      field: "options",
      before: beforeOptions,
      after: afterOptions,
    });
  }

  if (fieldChanges.length === 0) {
    return null;
  }

  return {
    row: rowIndex,
    titleBefore: normalizeText(beforeQuestion?.title),
    titleAfter: normalizeText(afterQuestion?.title),
    changedFields: fieldChanges.map((item) => item.field),
    fieldChanges,
  };
}

function buildQuestionDiffs(beforeQuestions, afterQuestions) {
  const maxLength = Math.max(beforeQuestions.length, afterQuestions.length);
  const changes = [];
  let addedCount = 0;
  let removedCount = 0;
  for (let index = 0; index < maxLength; index += 1) {
    const beforeQuestion = beforeQuestions[index];
    const afterQuestion = afterQuestions[index];
    if (!beforeQuestion && afterQuestion) {
      addedCount += 1;
      changes.push({
        row: index + 1,
        titleBefore: "",
        titleAfter: normalizeText(afterQuestion.title),
        changedFields: ["row_added"],
        fieldChanges: [{ field: "row_added", before: null, after: afterQuestion }],
      });
      continue;
    }
    if (beforeQuestion && !afterQuestion) {
      removedCount += 1;
      changes.push({
        row: index + 1,
        titleBefore: normalizeText(beforeQuestion.title),
        titleAfter: "",
        changedFields: ["row_removed"],
        fieldChanges: [{ field: "row_removed", before: beforeQuestion, after: null }],
      });
      continue;
    }
    const questionDiff = diffQuestion(beforeQuestion, afterQuestion, index + 1);
    if (questionDiff) {
      changes.push(questionDiff);
    }
  }
  return { changes, addedCount, removedCount };
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  const beforePayload = exportCurrentPayload(options.workbook);
  const afterPayload = loadCandidatePayload(options.jsonFile);
  const defaultChanges = diffDefaults(beforePayload.defaults || {}, afterPayload.defaults || {});
  const questionDiff = buildQuestionDiffs(beforePayload.questions || [], afterPayload.questions || []);
  const allChanges = [
    ...defaultChanges.map((item) => ({
      row: 0,
      titleBefore: "",
      titleAfter: "",
      changedFields: [item.field],
      fieldChanges: [item],
      scope: "defaults",
    })),
    ...questionDiff.changes,
  ];
  const visibleChanges = options.previewAll ? allChanges : allChanges.slice(0, options.limit);

  console.log(
    JSON.stringify(
      {
        status: "ok",
        workbook: options.workbook,
        jsonFile: options.jsonFile,
        summary: {
          defaultFieldChangedCount: defaultChanges.length,
          questionChangedCount: questionDiff.changes.length - questionDiff.addedCount - questionDiff.removedCount,
          addedCount: questionDiff.addedCount,
          removedCount: questionDiff.removedCount,
          totalChangedCount: allChanges.length,
        },
        preview: {
          previewAll: options.previewAll,
          limit: options.previewAll ? 0 : options.limit,
          changes: visibleChanges,
        },
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
