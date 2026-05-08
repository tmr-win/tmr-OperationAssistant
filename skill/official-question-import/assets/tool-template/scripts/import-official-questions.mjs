#!/usr/bin/env node

import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import * as XLSX from "xlsx";

const DATA_SHEET_NAME = "题目列表";
const DEFAULT_VALUE_SHEET_NAME = "默认值";
const INSTRUCTION_SHEET_NAME = "填写说明";
const DEFAULT_REPORT_DIR = "reports/official-question-import";
const MAX_BATCH_SIZE = 200;
const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_NAIVE_TIMEZONE_OFFSET = "+08:00";
const DEFAULT_OPS_ADMIN_BASE_URL = "https://admin.tmr.win/admin/questions/list";
const DEFAULT_SUBMIT_CONCURRENCY = 6;
const DUPLICATE_ERROR_CODES = new Set([
  "OFFICIAL_QUESTION_DUPLICATE_SAME_DAY",
  "OFFICIAL_QUESTION_PENDING_REVEAL_EXISTS",
]);

const HEADER_ALIASES = {
  candidateQuestionId: ["候选题ID", "候选题目ID", "candidatequestionid"],
  title: ["题目", "title"],
  titleEn: ["英文题目", "题目英文", "titleen", "englishtitle", "titleenglish"],
  category: ["分类", "题目分类", "category"],
  sourceUrl: ["问题来源地址", "来源地址", "题目来源地址", "sourceurl"],
  deadlineAt: ["截止时间", "deadlineat"],
  announceAt: ["开奖时间", "announceat", "resolvedat"],
  scheduledPublishAt: ["定时发布时间", "scheduledpublishat"],
  imageFile: ["图片文件名", "图片", "image", "imagefile", "imagefilename"],
};

const DEFAULT_VALUE_ALIASES = {
  category: ["默认分类", "分类", "defaultcategory", "category"],
  sourceUrl: ["默认来源地址", "默认题目来源地址", "问题来源地址", "来源地址", "defaultsourceurl", "sourceurl"],
  announceAt: ["默认开奖时间", "开奖时间", "defaultannounceat", "announceat"],
  scheduledPublishAt: ["默认定时发布时间", "定时发布时间", "defaultscheduledpublishat", "scheduledpublishat"],
};

const DEFAULT_VALUE_KEY_ALIASES = {
  key: ["字段", "键", "配置项", "key", "name"],
  value: ["值", "默认值", "value"],
};

function printUsage() {
  console.log(`用法：
  node scripts/import-official-questions.mjs <validate|plan|submit> <文件路径> [选项]
  node scripts/import-official-questions.mjs template <输出路径>

示例：
  node scripts/import-official-questions.mjs validate ./questions.xlsx
  node scripts/import-official-questions.mjs plan ./questions.xlsx --default-category 金融
  node scripts/import-official-questions.mjs submit ./questions.xlsx
  node scripts/import-official-questions.mjs submit ./questions.xlsx --base-url https://admin.dev.tmr.win --token <TOKEN> --images-dir ./images
  node scripts/import-official-questions.mjs template ./official-question-template.xlsx

选项：
  --base-url <地址>                  后台域名、网关根地址或 /admin/questions/list 页面地址；脚本会自动识别
  --token <令牌>                     运营后台 Bearer Token；也可通过环境变量 OPS_ADMIN_ACCESS_TOKEN 传入
  --email <邮箱>                     兼容旧流程的账号参数；runtime skill 默认优先走账号密码登录
  --password <密码>                  兼容旧流程的密码参数；runtime skill 默认优先走账号密码登录
  --images-dir <目录>                图片目录；需要配合“图片文件名”列使用
  --report-dir <目录>                报告输出目录，默认 ${DEFAULT_REPORT_DIR}
  --default-category <值>            默认分类
  --default-source-url <值>          默认题目来源地址
  --default-announce-at <时间>       默认开奖时间，示例 2026-05-01 10:00
  --default-scheduled-publish-at <时间>
                                    默认定时发布时间
  --batch-id-prefix <前缀>           提交时的 batch_id 前缀，默认 ops-import
  --submit-concurrency <数量>       submit 时并发提交题目数，默认 ${DEFAULT_SUBMIT_CONCURRENCY}
  --timeout-ms <毫秒>                请求超时，默认 ${DEFAULT_TIMEOUT_MS}
  --help                            查看帮助
`);
}

function normalizeHeaderKey(value) {
  return String(value).trim().toLowerCase().replace(/[\s_\-()（）:：]/g, "");
}

function normalizeText(value) {
  if (value == null) {
    return "";
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  return String(value).trim();
}

function parseArgs(argv) {
  if (argv.includes("--help") || argv.includes("-h")) {
    printUsage();
    process.exit(0);
  }

  const [command, filePath, ...rest] = argv;
  if (!command || !filePath) {
    printUsage();
    throw new Error("请至少提供命令和文件路径");
  }
  if (!["validate", "plan", "submit", "template"].includes(command)) {
    throw new Error(`不支持的命令：${command}`);
  }

  const options = {
    baseUrl: DEFAULT_OPS_ADMIN_BASE_URL,
    token: process.env.OPS_ADMIN_ACCESS_TOKEN || "",
    email: process.env.OPS_ADMIN_EMAIL || "",
    password: process.env.OPS_ADMIN_PASSWORD || "",
    imagesDir: "",
    reportDir: DEFAULT_REPORT_DIR,
    defaultCategory: "",
    defaultSourceUrl: "",
    defaultAnnounceAt: "",
    defaultScheduledPublishAt: "",
    batchIdPrefix: "ops-import",
    submitConcurrency: DEFAULT_SUBMIT_CONCURRENCY,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  };

  for (let index = 0; index < rest.length; index += 2) {
    const key = rest[index];
    const value = rest[index + 1];
    if (!key.startsWith("--")) {
      throw new Error(`无法识别的参数：${key}`);
    }
    if (value == null || value.startsWith("--")) {
      throw new Error(`参数 ${key} 缺少取值`);
    }
    switch (key) {
      case "--base-url":
        options.baseUrl = value;
        break;
      case "--token":
        options.token = value;
        break;
      case "--email":
        options.email = value;
        break;
      case "--password":
        options.password = value;
        break;
      case "--images-dir":
        options.imagesDir = value;
        break;
      case "--report-dir":
        options.reportDir = value;
        break;
      case "--default-category":
        options.defaultCategory = value;
        break;
      case "--default-source-url":
        options.defaultSourceUrl = value;
        break;
      case "--default-announce-at":
        options.defaultAnnounceAt = value;
        break;
      case "--default-scheduled-publish-at":
        options.defaultScheduledPublishAt = value;
        break;
      case "--batch-id-prefix":
        options.batchIdPrefix = value;
        break;
      case "--submit-concurrency":
        options.submitConcurrency = Number(value);
        if (!Number.isInteger(options.submitConcurrency) || options.submitConcurrency <= 0) {
          throw new Error("submit-concurrency 必须是正整数");
        }
        break;
      case "--timeout-ms":
        options.timeoutMs = Number(value);
        if (!Number.isFinite(options.timeoutMs) || options.timeoutMs <= 0) {
          throw new Error("timeout-ms 必须是正整数");
        }
        break;
      default:
        throw new Error(`不支持的参数：${key}`);
    }
  }

  return {
    command,
    filePath: path.resolve(filePath),
    options: {
      ...options,
      imagesDir: options.imagesDir ? path.resolve(options.imagesDir) : "",
      reportDir: path.resolve(options.reportDir),
    },
  };
}

function buildOfficialQuestionId(deadlineAtIso, title) {
  const deadline = new Date(deadlineAtIso);
  const year = String(deadline.getUTCFullYear());
  const month = String(deadline.getUTCMonth() + 1).padStart(2, "0");
  const day = String(deadline.getUTCDate()).padStart(2, "0");
  const hour = String(deadline.getUTCHours()).padStart(2, "0");
  const normalizedTitle = title.trim().toLowerCase().replace(/\s+/g, "-");
  const titleHash = createHash("sha1").update(normalizedTitle).digest("hex").slice(0, 12);
  return `official-${year}${month}${day}${hour}-${titleHash}`;
}

function resolveBaseUrl(baseUrl) {
  const gatewayRootUrl = resolveGatewayRootUrl(baseUrl);
  if (!gatewayRootUrl) {
    return "";
  }
  return `${gatewayRootUrl}/intention-market`;
}

function resolveGatewayRootUrl(baseUrl) {
  const normalized = String(baseUrl || "").trim();
  if (!normalized) {
    return "";
  }

  try {
    const parsed = new URL(normalized);
    let pathname = parsed.pathname.replace(/\/+$/, "");
    if (pathname.endsWith("/intention-market")) {
      pathname = pathname.slice(0, -"/intention-market".length);
    } else if (pathname === "/") {
      pathname = "";
    } else {
      pathname = pathname.replace(/\/admin(?:\/.*)?$/, "");
    }
    return `${parsed.origin}${pathname}`;
  } catch {
    return normalized
      .replace(/\/+$/, "")
      .replace(/\/admin(?:\/.*)?$/, "")
      .replace(/\/intention-market$/, "");
  }
}

function unwrapApiPayload(payload) {
  if (
    payload
    && typeof payload === "object"
    && !Array.isArray(payload)
    && Object.prototype.hasOwnProperty.call(payload, "data")
  ) {
    return payload.data ?? null;
  }
  return payload;
}

function maskEmail(email) {
  const normalized = String(email || "").trim();
  const [localPart = "", domainPart = ""] = normalized.split("@");
  if (!localPart || !domainPart) {
    return normalized;
  }
  if (localPart.length <= 2) {
    return `${localPart[0] || "*"}***@${domainPart}`;
  }
  return `${localPart.slice(0, 2)}***@${domainPart}`;
}

function getPreferredSheetName(workbook) {
  if (workbook.SheetNames.includes(DATA_SHEET_NAME)) {
    return DATA_SHEET_NAME;
  }
  return workbook.SheetNames[1] || workbook.SheetNames[0];
}

function getDefaultValueSheetName(workbook) {
  if (workbook.SheetNames.includes(DEFAULT_VALUE_SHEET_NAME)) {
    return DEFAULT_VALUE_SHEET_NAME;
  }
  return "";
}

function buildTemplateWorkbook() {
  const workbook = XLSX.utils.book_new();

  const instructionSheet = XLSX.utils.aoa_to_sheet([
    ["运营官方题目导题模板"],
    ["请按顺序填写“默认值”和“题目列表”两个 sheet。"],
    [""],
    ["sheet", "用途", "说明"],
    [INSTRUCTION_SHEET_NAME, "使用说明", "仅阅读，不参与导题"],
    [DEFAULT_VALUE_SHEET_NAME, "整批默认值", "分类、开奖时间、定时发布时间、来源地址可以只填一次"],
    [DATA_SHEET_NAME, "题目数据", "每行一题；单行填写优先级最高"],
    [""],
    ["推荐流程"],
    ["1. 先填写默认值 sheet，可留空不用。"],
    ["2. 题目列表第 2 行是示例题，正式导题前请删除或改成真实题目。"],
    ["3. 再到题目列表逐行填题。"],
    ["4. 先运行 validate，再运行 plan，最后 submit。"],
    [""],
    ["命令示例"],
    ["npm run import:official-questions -- validate ./questions.xlsx"],
    ["npm run import:official-questions -- plan ./questions.xlsx"],
    ["npm run import:official-questions -- submit ./questions.xlsx --base-url https://admin.dev.tmr.win --token <TOKEN>"],
    [""],
    ["字段说明", "是否必填", "备注"],
    ["题目", "是", "中文题目"],
    ["英文题目", "是", "英文题目"],
    ["分类", "否", "留空时可继承默认值 sheet 的默认分类"],
    ["问题来源地址", "否", "留空时可继承默认值 sheet 的默认来源地址"],
    ["选项1 / 英文选项1", "是", "至少 2 个选项，且中英成对"],
    ["选项2 / 英文选项2", "是", "至少 2 个选项，且中英成对"],
    ["截止时间", "是", "示例：2026-04-30 16:00"],
    ["开奖时间", "否", "留空时可继承默认值 sheet 的默认开奖时间"],
    ["定时发布时间", "否", "留空时可继承默认值 sheet 的默认定时发布时间"],
    ["候选题ID", "否", "如需直接采纳候选题，可填写候选题 UUID；填写后该行会按“采纳候选题”模式导入"],
    ["图片文件名", "否", "仅填写文件名，例如 btc-close-above-100k.png；提交时配合 --images-dir 指向图片目录"],
    [""],
    ["补充规则"],
    ["1. 单行自己填写的值优先级最高，会覆盖默认值 sheet 和命令行默认参数。"],
    ["2. 候选题ID、图片文件名都不是必填；不填时脚本会按普通手工题处理。"],
    ["3. 图片不会阻塞题目主体导入，但图片缺失会在报告里单独标红。"],
    ["4. 如需更多选项，可继续追加“选项3 / 英文选项3”“选项4 / 英文选项4”列。"],
  ]);

  const defaultValueSheet = XLSX.utils.aoa_to_sheet([
    ["字段", "值"],
    ["默认分类", "金融"],
    ["默认来源地址", "https://example.com/default-source"],
    ["默认开奖时间", "2026-05-01 10:00"],
    ["默认定时发布时间", "2026-04-28 10:00"],
    [""],
    ["也支持另一种写法：直接把表头写成“默认分类 / 默认开奖时间 / 默认定时发布时间 / 默认来源地址”，第二行填值。", ""],
  ]);

  const dataSheet = XLSX.utils.aoa_to_sheet([
    [
      "题目",
      "英文题目",
      "分类",
      "问题来源地址",
      "选项1",
      "英文选项1",
      "选项2",
      "英文选项2",
      "截止时间",
      "开奖时间",
      "定时发布时间",
      "候选题ID",
      "图片文件名",
    ],
    [
      "比特币本月收盘价是否高于10万美元？",
      "Will Bitcoin close above $100,000 this month?",
      "",
      "https://example.com/questions/btc-close-above-100k",
      "是",
      "Yes",
      "否",
      "No",
      "2026-04-30 16:00",
      "",
      "",
      "",
      "btc-close-above-100k.png",
    ],
    ["", "", "", "", "", "", "", "", "", "", "", "", ""],
  ]);

  XLSX.utils.book_append_sheet(workbook, instructionSheet, INSTRUCTION_SHEET_NAME);
  XLSX.utils.book_append_sheet(workbook, defaultValueSheet, DEFAULT_VALUE_SHEET_NAME);
  XLSX.utils.book_append_sheet(workbook, dataSheet, DATA_SHEET_NAME);
  return workbook;
}

function getNormalizedRow(row) {
  const normalized = new Map();
  Object.entries(row).forEach(([key, value]) => {
    normalized.set(normalizeHeaderKey(key), value);
  });
  return normalized;
}

function getCell(normalizedRow, aliases) {
  for (const alias of aliases) {
    const value = normalizedRow.get(normalizeHeaderKey(alias));
    const text = normalizeText(value);
    if (text) {
      return text;
    }
  }
  return "";
}

function extractDefaultsFromKeyValueRows(rows) {
  const defaults = {};
  for (const row of rows) {
    const normalizedRow = getNormalizedRow(row);
    const keyText = getCell(normalizedRow, DEFAULT_VALUE_KEY_ALIASES.key);
    const valueText = getCell(normalizedRow, DEFAULT_VALUE_KEY_ALIASES.value);
    if (!keyText || !valueText) {
      continue;
    }
    const normalizedKey = normalizeHeaderKey(keyText);
    for (const [field, aliases] of Object.entries(DEFAULT_VALUE_ALIASES)) {
      if (aliases.some((alias) => normalizeHeaderKey(alias) === normalizedKey)) {
        defaults[field] = valueText;
        break;
      }
    }
  }
  return defaults;
}

function extractDefaultsFromHeaderRow(rows) {
  if (rows.length === 0) {
    return {};
  }
  const normalizedRow = getNormalizedRow(rows[0]);
  return {
    category: getCell(normalizedRow, DEFAULT_VALUE_ALIASES.category),
    sourceUrl: getCell(normalizedRow, DEFAULT_VALUE_ALIASES.sourceUrl),
    announceAt: getCell(normalizedRow, DEFAULT_VALUE_ALIASES.announceAt),
    scheduledPublishAt: getCell(normalizedRow, DEFAULT_VALUE_ALIASES.scheduledPublishAt),
  };
}

function mergeDefaultValues(...sources) {
  const merged = {
    category: "",
    sourceUrl: "",
    announceAt: "",
    scheduledPublishAt: "",
  };

  for (const source of sources) {
    if (!source) {
      continue;
    }
    for (const [key, value] of Object.entries(source)) {
      if (value) {
        merged[key] = value;
      }
    }
  }

  return merged;
}

function resolveOptionColumnIndex(key) {
  const patterns = [
    /^选项(\d+)$/,
    /^option(\d+)(?:label)?$/,
    /^英文选项(\d+)$/,
    /^选项(\d+)英文$/,
    /^option(\d+)en$/,
    /^option(\d+)english$/,
    /^option(\d+)labelen$/,
  ];
  for (const pattern of patterns) {
    const matched = key.match(pattern);
    if (matched) {
      return Number(matched[1]);
    }
  }
  return null;
}

function isEnglishOptionColumn(key) {
  return (
    /^英文选项\d+$/.test(key)
    || /^选项\d+英文$/.test(key)
    || /^option\d+en$/.test(key)
    || /^option\d+english$/.test(key)
    || /^option\d+labelen$/.test(key)
  );
}

function parseOptionsFromRow(normalizedRow) {
  const optionBuckets = new Map();
  normalizedRow.forEach((value, key) => {
    const index = resolveOptionColumnIndex(key);
    if (index == null) {
      return;
    }
    const text = normalizeText(value);
    if (!text) {
      return;
    }
    const bucket = optionBuckets.get(index) || { label: "", labelEn: "" };
    if (isEnglishOptionColumn(key)) {
      bucket.labelEn = text;
    } else {
      bucket.label = text;
    }
    optionBuckets.set(index, bucket);
  });

  return Array.from(optionBuckets.entries())
    .sort((left, right) => left[0] - right[0])
    .map(([, option]) => ({
      label: option.label.trim(),
      labelEn: option.labelEn.trim(),
    }))
    .filter((option) => option.label || option.labelEn);
}

function normalizeDateTimeInput(value) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "";
  }
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return normalized;
  }
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function toIsoString(value, fieldLabel) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    throw new Error(`${fieldLabel}不能为空`);
  }
  const date = parseDateTimeValue(normalized);
  if (Number.isNaN(date.getTime())) {
    throw new Error(`${fieldLabel}格式无效`);
  }
  return date.toISOString();
}

function parseDateTimeValue(value) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return new Date(Number.NaN);
  }

  if (/(?:[zZ]|[+\-]\d{2}:\d{2})$/.test(normalized)) {
    return new Date(normalized);
  }

  const matched = normalized
    .replaceAll("/", "-")
    .match(
      /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$/,
    );
  if (matched) {
    const [, year, month, day, hour = "00", minute = "00", second = "00"] = matched;
    return new Date(
      `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:${String(second).padStart(2, "0")}${DEFAULT_NAIVE_TIMEZONE_OFFSET}`,
    );
  }

  return new Date(normalized);
}

function chunkArray(items, size) {
  const chunks = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

function parseCsvText(content) {
  const rows = [];
  let currentRow = [];
  let currentCell = "";
  let inQuotes = false;

  for (let index = 0; index < content.length; index += 1) {
    const char = content[index];
    const nextChar = content[index + 1];

    if (char === "\"") {
      if (inQuotes && nextChar === "\"") {
        currentCell += "\"";
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === "," && !inQuotes) {
      currentRow.push(currentCell);
      currentCell = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && nextChar === "\n") {
        index += 1;
      }
      currentRow.push(currentCell);
      rows.push(currentRow);
      currentRow = [];
      currentCell = "";
      continue;
    }

    currentCell += char;
  }

  if (currentCell || currentRow.length > 0) {
    currentRow.push(currentCell);
    rows.push(currentRow);
  }

  return rows;
}

function buildRowsFromCsvMatrix(matrix) {
  const [headerRow = [], ...dataRows] = matrix;
  const headers = headerRow.map((item) => String(item || "").trim());
  return dataRows
    .map((row) => {
      const record = {};
      headers.forEach((header, index) => {
        record[header || `column_${index + 1}`] = row[index] ?? "";
      });
      return record;
    })
    .filter((row) => Object.values(row).some((value) => normalizeText(value)));
}

async function readSourcePayload(filePath) {
  const fileExtension = path.extname(filePath).toLowerCase();
  if (fileExtension === ".csv" || fileExtension === ".txt") {
    return {
      rows: buildRowsFromCsvMatrix(
        parseCsvText(await fs.readFile(filePath, "utf8")),
      ),
      sheetDefaults: {
        category: "",
        sourceUrl: "",
        announceAt: "",
        scheduledPublishAt: "",
      },
    };
  }

  const workbook = XLSX.read(await fs.readFile(filePath), {
    type: "buffer",
    cellDates: true,
    raw: false,
  });
  const sheetName = getPreferredSheetName(workbook);
  if (!sheetName) {
    throw new Error("未找到可读取的工作表");
  }
  const sheet = workbook.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json(sheet, {
    defval: "",
    raw: false,
  });
  const defaultSheetName = getDefaultValueSheetName(workbook);
  let sheetDefaults = {
    category: "",
    sourceUrl: "",
    announceAt: "",
    scheduledPublishAt: "",
  };
  if (defaultSheetName) {
    const defaultSheetRows = XLSX.utils.sheet_to_json(workbook.Sheets[defaultSheetName], {
      defval: "",
      raw: false,
    }).filter((row) =>
      Object.values(row).some((value) => normalizeText(value)),
    );
    sheetDefaults = mergeDefaultValues(
      extractDefaultsFromHeaderRow(defaultSheetRows),
      extractDefaultsFromKeyValueRows(defaultSheetRows),
    );
  }

  return {
    rows: rows.filter((row) =>
      Object.values(row).some((value) => normalizeText(value)),
    ),
    sheetDefaults,
  };
}

async function buildPreparedRows(rows, options, defaults) {
  const preparedRows = [];
  const validationErrors = [];

  for (const [rowIndex, row] of rows.entries()) {
    const rowNumber = rowIndex + 2;
    const normalizedRow = getNormalizedRow(row);
    const title = getCell(normalizedRow, HEADER_ALIASES.title);
    const titleEn = getCell(normalizedRow, HEADER_ALIASES.titleEn);
    const category = getCell(normalizedRow, HEADER_ALIASES.category) || defaults.category;
    const sourceUrl = getCell(normalizedRow, HEADER_ALIASES.sourceUrl) || defaults.sourceUrl;
    const deadlineAt = normalizeDateTimeInput(
      getCell(normalizedRow, HEADER_ALIASES.deadlineAt),
    );
    const announceAt = normalizeDateTimeInput(
      getCell(normalizedRow, HEADER_ALIASES.announceAt) || defaults.announceAt,
    );
    const scheduledPublishAt = normalizeDateTimeInput(
      getCell(normalizedRow, HEADER_ALIASES.scheduledPublishAt) || defaults.scheduledPublishAt,
    );
    const candidateQuestionId = getCell(
      normalizedRow,
      HEADER_ALIASES.candidateQuestionId,
    );
    const imageFileName = getCell(normalizedRow, HEADER_ALIASES.imageFile);
    const optionsList = parseOptionsFromRow(normalizedRow);

    const rowErrors = [];
    if (!title) {
      rowErrors.push("题目不能为空");
    }
    if (!titleEn) {
      rowErrors.push("英文题目不能为空");
    }
    if (!category) {
      rowErrors.push("分类不能为空；请在表格中填写或通过 --default-category 指定");
    }
    if (!deadlineAt) {
      rowErrors.push("截止时间不能为空");
    }
    if (!announceAt) {
      rowErrors.push("开奖时间不能为空；请在表格中填写或通过 --default-announce-at 指定");
    }
    if (optionsList.length < 2) {
      rowErrors.push("至少需要 2 个有效选项");
    }
    optionsList.forEach((option, optionIndex) => {
      if (!option.label) {
        rowErrors.push(`第 ${optionIndex + 1} 个选项缺少中文文案`);
      }
      if (!option.labelEn) {
        rowErrors.push(`第 ${optionIndex + 1} 个选项缺少英文文案`);
      }
    });

    let deadlineAtIso = "";
    let announceAtIso = "";
    let scheduledPublishAtIso = "";
    if (deadlineAt) {
      try {
        deadlineAtIso = toIsoString(deadlineAt, `第 ${rowNumber} 行截止时间`);
      } catch (error) {
        rowErrors.push(error.message);
      }
    }
    if (announceAt) {
      try {
        announceAtIso = toIsoString(announceAt, `第 ${rowNumber} 行开奖时间`);
      } catch (error) {
        rowErrors.push(error.message);
      }
    }
    if (scheduledPublishAt) {
      try {
        scheduledPublishAtIso = toIsoString(
          scheduledPublishAt,
          `第 ${rowNumber} 行定时发布时间`,
        );
      } catch (error) {
        rowErrors.push(error.message);
      }
    }

    if (deadlineAtIso && announceAtIso) {
      if (new Date(deadlineAtIso).getTime() >= new Date(announceAtIso).getTime()) {
        rowErrors.push("开奖时间必须晚于截止时间");
      }
    }
    if (scheduledPublishAtIso && deadlineAtIso) {
      if (new Date(scheduledPublishAtIso).getTime() > new Date(deadlineAtIso).getTime()) {
        rowErrors.push("定时发布时间不能晚于截止时间");
      }
    }

    const imagePath = imageFileName && options.imagesDir
      ? path.resolve(options.imagesDir, imageFileName)
      : "";

    if (imageFileName && options.imagesDir) {
      try {
        await fs.access(imagePath);
      } catch {
        rowErrors.push(`图片不存在：${imagePath}`);
      }
    }

    preparedRows.push({
      rowNumber,
      title,
      titleEn,
      category,
      sourceUrl,
      deadlineAtIso,
      announceAtIso,
      scheduledPublishAtIso,
      candidateQuestionId: candidateQuestionId || null,
      imageFileName,
      imagePath,
      options: optionsList,
      officialQuestionId: deadlineAtIso && title
        ? buildOfficialQuestionId(deadlineAtIso, title)
        : "",
      payload: {
        candidate_question_id: candidateQuestionId || undefined,
        title,
        title_en: titleEn,
        source_url: sourceUrl || undefined,
        category,
        deadline_at: deadlineAtIso,
        announce_at: announceAtIso,
        scheduled_publish_at: scheduledPublishAtIso || undefined,
        options: optionsList.map((option, optionIndex) => ({
          key: String.fromCharCode(65 + optionIndex),
          label: option.label,
          label_en: option.labelEn,
        })),
      },
      rowErrors,
    });

    if (rowErrors.length > 0) {
      validationErrors.push({
        rowNumber,
        title,
        errors: rowErrors,
      });
    }
  }

  return { preparedRows, validationErrors };
}

function printValidationSummary(preparedRows, validationErrors) {
  const scheduledCount = preparedRows.filter((item) => item.scheduledPublishAtIso).length;
  const imageCount = preparedRows.filter((item) => item.imageFileName).length;
  const candidateCount = preparedRows.filter((item) => item.candidateQuestionId).length;
  console.log(`共读取 ${preparedRows.length} 条题目`);
  console.log(`- 定时发布：${scheduledCount} 条`);
  console.log(`- 候选题采纳：${candidateCount} 条`);
  console.log(`- 声明图片：${imageCount} 条`);
  if (validationErrors.length === 0) {
    console.log("校验通过，没有发现格式错误。");
    return;
  }

  console.log(`校验失败，共 ${validationErrors.length} 行有问题：`);
  validationErrors.forEach((item) => {
    const title = item.title ? `《${item.title}》` : "未填写题目";
    console.log(`- 第 ${item.rowNumber} 行 ${title}`);
    item.errors.forEach((error) => {
      console.log(`  - ${error}`);
    });
  });
}

function printPlan(preparedRows, defaults) {
  const batches = chunkArray(preparedRows, MAX_BATCH_SIZE);
  const defaultEntries = [
    defaults.category ? `分类=${defaults.category}` : "",
    defaults.sourceUrl ? `来源地址=${defaults.sourceUrl}` : "",
    defaults.announceAt ? `开奖时间=${normalizeDateTimeInput(defaults.announceAt)}` : "",
    defaults.scheduledPublishAt ? `定时发布时间=${normalizeDateTimeInput(defaults.scheduledPublishAt)}` : "",
  ].filter(Boolean);
  if (defaultEntries.length > 0) {
    console.log(`默认值：${defaultEntries.join("；")}`);
  }
  console.log(`预计分 ${batches.length} 批提交，每批最多 ${MAX_BATCH_SIZE} 条。`);
  console.log("前 10 条预览：");
  preparedRows.slice(0, 10).forEach((item) => {
    const publishLabel = item.scheduledPublishAtIso
      ? `定时发布 ${formatDisplayDateTime(item.scheduledPublishAtIso)}`
      : "待发布";
    const imageLabel = item.imageFileName ? `，图片 ${item.imageFileName}` : "";
    console.log(`- 第 ${item.rowNumber} 行《${item.title}》 / ${publishLabel}${imageLabel}`);
  });
}

function formatDisplayDateTime(isoString) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(isoString));
}

function createTimeoutSignal(timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return {
    signal: controller.signal,
    cleanup() {
      clearTimeout(timer);
    },
  };
}

async function requestJson({ url, method, token, body, timeoutMs }) {
  const { signal, cleanup } = createTimeoutSignal(timeoutMs);
  try {
    const headers = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(url, {
      method,
      headers,
      body: JSON.stringify(body),
      signal,
    });
    const rawText = await response.text();
    let payload = null;
    if (rawText) {
      try {
        payload = JSON.parse(rawText);
      } catch {
        payload = rawText;
      }
    }
    if (!response.ok) {
      const message = payload?.message
        || payload?.detail?.message
        || payload?.detail
        || `请求失败，状态码 ${response.status}`;
      throw new Error(String(message));
    }
    return unwrapApiPayload(payload);
  } finally {
    cleanup();
  }
}

async function loginOpsAdmin({ gatewayRootUrl, email, password, timeoutMs }) {
  const payload = await requestJson({
    url: `${gatewayRootUrl}/identity-service/api/v1/auth/ops-admin/password/login`,
    method: "POST",
    timeoutMs,
    body: {
      email,
      password,
    },
  });
  if (!payload?.access_token) {
    throw new Error("运营后台登录成功，但未返回 access_token");
  }
  return payload.access_token;
}

async function uploadImage({ url, token, imagePath, timeoutMs }) {
  const imageBuffer = await fs.readFile(imagePath);
  const formData = new FormData();
  formData.append(
    "image",
    new Blob([imageBuffer]),
    path.basename(imagePath),
  );

  const { signal, cleanup } = createTimeoutSignal(timeoutMs);
  try {
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
      signal,
    });
    const rawText = await response.text();
    let payload = null;
    if (rawText) {
      try {
        payload = JSON.parse(rawText);
      } catch {
        payload = rawText;
      }
    }
    if (!response.ok) {
      const message = payload?.message
        || payload?.detail?.message
        || payload?.detail
        || `上传失败，状态码 ${response.status}`;
      throw new Error(String(message));
    }
    return unwrapApiPayload(payload);
  } finally {
    cleanup();
  }
}

function buildReportRecord(baseRecord) {
  return {
    row_number: baseRecord.rowNumber,
    title: baseRecord.title,
    official_question_id: baseRecord.officialQuestionId,
    action: "pending",
    question_id: null,
    import_message: null,
    import_error: null,
    image_file: baseRecord.imageFileName || null,
    image_uploaded: false,
    image_message: null,
  };
}

function normalizeSubmitRecord(resultItem, fallbackMatch, sourceItem, responseItems) {
  const record = buildReportRecord(sourceItem);
  if (!resultItem) {
    record.action = "receipt_incomplete";
    record.import_error = "missing_batch_result";
    record.import_message = `后台已收到该题提交请求，但单题回执不完整，未继续自动猜测是否已入库。${summarizeBatchResultIds(responseItems)}`;
    return record;
  }

  const rawAction = normalizeText(resultItem.action || "failed").toLowerCase();
  const importError = fallbackMatch?.importError || resultItem.error_code || null;
  let action = rawAction || "failed";
  if (action === "failed" && DUPLICATE_ERROR_CODES.has(importError || "")) {
    action = "duplicate";
  }

  record.action = action;
  record.question_id = resultItem.question_id || null;
  record.import_message = fallbackMatch?.importMessage || resultItem.message || null;
  record.import_error = importError;
  record.official_question_id = resultItem.official_question_id || record.official_question_id;
  return record;
}

function updateSummaryByRecord(summary, record) {
  if (record.action === "inserted") {
    summary.inserted += 1;
    return;
  }
  if (record.action === "updated") {
    summary.updated += 1;
    return;
  }
  if (record.action === "skipped") {
    summary.skipped += 1;
    return;
  }
  if (record.action === "duplicate") {
    summary.duplicate += 1;
    return;
  }
  if (record.action === "receipt_incomplete") {
    summary.receipt_incomplete += 1;
    return;
  }
  summary.failed += 1;
}

function normalizeOfficialQuestionId(value) {
  return String(value || "").trim();
}

function buildBatchResultItemMap(responseItems) {
  const resultItemMap = new Map();
  responseItems.forEach((item) => {
    const officialQuestionId = normalizeOfficialQuestionId(item?.official_question_id);
    if (!officialQuestionId) {
      return;
    }
    const items = resultItemMap.get(officialQuestionId) || [];
    items.push(item);
    resultItemMap.set(officialQuestionId, items);
  });
  return resultItemMap;
}

function consumeBatchResultItem(resultItemMap, officialQuestionId) {
  const normalizedOfficialQuestionId = normalizeOfficialQuestionId(officialQuestionId);
  if (!normalizedOfficialQuestionId) {
    return null;
  }
  const matchedItems = resultItemMap.get(normalizedOfficialQuestionId) || [];
  if (matchedItems.length === 0) {
    return null;
  }
  const matchedItem = matchedItems.shift();
  if (matchedItems.length === 0) {
    resultItemMap.delete(normalizedOfficialQuestionId);
  }
  return matchedItem;
}

function summarizeBatchResultIds(responseItems) {
  const ids = responseItems
    .map((item) => normalizeOfficialQuestionId(item?.official_question_id))
    .filter(Boolean);
  if (ids.length === 0) {
    return "回执 items 中没有可用的 official_question_id";
  }
  const preview = ids.slice(0, 5).join(", ");
  if (ids.length <= 5) {
    return `回执返回的 official_question_id: ${preview}`;
  }
  return `回执返回的 official_question_id: ${preview} 等 ${ids.length} 个`;
}

function resolveFallbackBatchResultItem(batch, responseItems, sourceItem) {
  if (batch.length !== 1 || responseItems.length !== 1) {
    return null;
  }

  const onlyItem = responseItems[0] || null;
  if (onlyItem == null) {
    return null;
  }

  const returnedOfficialQuestionId = normalizeOfficialQuestionId(onlyItem.official_question_id);
  const hasStructuredResult = returnedOfficialQuestionId
    || onlyItem.question_id
    || onlyItem.action
    || onlyItem.error_code
    || onlyItem.message;
  if (!hasStructuredResult) {
    return null;
  }

  let importError = null;
  let importMessage = null;
  if (!returnedOfficialQuestionId) {
    importError = "missing_official_question_id_in_batch_result";
    importMessage = `单题批次已收到回执，但回执缺少 official_question_id。${summarizeBatchResultIds(responseItems)}`;
  } else if (returnedOfficialQuestionId !== sourceItem.officialQuestionId) {
    importError = "official_question_id_mismatch";
    importMessage = `单题批次回执中的 official_question_id 与请求不一致：expected=${sourceItem.officialQuestionId}, actual=${returnedOfficialQuestionId}`;
  }

  return {
    resultItem: onlyItem,
    importError,
    importMessage,
  };
}

async function writeReport(reportDir, report) {
  await fs.mkdir(reportDir, { recursive: true });
  const timestamp = new Date().toISOString().replaceAll(":", "").replace(/\.\d+Z$/, "Z");
  const jsonPath = path.join(reportDir, `import-${timestamp}.json`);
  const mdPath = path.join(reportDir, `import-${timestamp}.md`);

  await fs.writeFile(jsonPath, JSON.stringify(report, null, 2), "utf8");

  const lines = [
    `# 官方题目导题报告`,
    "",
    `- 生成时间：${report.generated_at}`,
    `- 源文件：${report.source_file}`,
    `- 提交模式：${report.command}`,
    `- 总行数：${report.summary.total}`,
    `- 插入：${report.summary.inserted}`,
    `- 更新：${report.summary.updated}`,
    `- 跳过：${report.summary.skipped}`,
    `- 重复未提交：${report.summary.duplicate}`,
    `- 回执不完整：${report.summary.receipt_incomplete}`,
    `- 失败：${report.summary.failed}`,
    `- 图片上传成功：${report.summary.image_uploaded}`,
    `- 图片上传失败：${report.summary.image_failed}`,
    "",
    `## 明细`,
    "",
    `| 行号 | 题目 | 导题结果 | question_id | 图片 | 备注 |`,
    `| --- | --- | --- | --- | --- | --- |`,
  ];

  report.items.forEach((item) => {
    const note = item.import_error || item.import_message || item.image_message || "";
    lines.push(
      `| ${item.row_number} | ${item.title || "-"} | ${item.action} | ${item.question_id || "-"} | ${item.image_uploaded ? "成功" : item.image_file ? "未上传/失败" : "-"} | ${note.replaceAll("|", "\\|")} |`,
    );
  });

  await fs.writeFile(mdPath, `${lines.join("\n")}\n`, "utf8");

  return { jsonPath, mdPath };
}

async function ensureImagePath(imagePath) {
  try {
    await fs.access(imagePath);
    return true;
  } catch {
    return false;
  }
}

async function submitSingleQuestion({
  sourceItem,
  itemIndex,
  totalCount,
  resolvedBaseUrl,
  accessToken,
  options,
}) {
  const batchId = `${options.batchIdPrefix}-${Date.now()}-${itemIndex + 1}`;
  console.log(`开始提交第 ${itemIndex + 1}/${totalCount} 题：第 ${sourceItem.rowNumber} 行《${sourceItem.title}》`);

  try {
    const response = await requestJson({
      url: `${resolvedBaseUrl}/api/v1/admin/market-questions/official/batch-upsert`,
      method: "POST",
      token: accessToken,
      timeoutMs: options.timeoutMs,
      body: {
        batch_id: batchId,
        questions: [sourceItem.payload],
      },
    });

    const responseItems = Array.isArray(response?.items) ? response.items : [];
    const matchedResultItem = consumeBatchResultItem(
      buildBatchResultItemMap(responseItems),
      sourceItem.officialQuestionId,
    );
    const fallbackMatch = matchedResultItem
      ? null
      : resolveFallbackBatchResultItem([sourceItem], responseItems, sourceItem);
    const resultItem = matchedResultItem || fallbackMatch?.resultItem || null;
    const record = normalizeSubmitRecord(resultItem, fallbackMatch, sourceItem, responseItems);

    if (record.question_id && sourceItem.imageFileName && options.imagesDir) {
      if (!(await ensureImagePath(sourceItem.imagePath))) {
        record.image_message = `图片不存在：${sourceItem.imagePath}`;
      } else {
        try {
          await uploadImage({
            url: `${resolvedBaseUrl}/api/v1/admin/crawler-questions/${record.question_id}/image`,
            token: accessToken,
            imagePath: sourceItem.imagePath,
            timeoutMs: options.timeoutMs,
          });
          record.image_uploaded = true;
          record.image_message = "上传成功";
        } catch (error) {
          record.image_message = error.message;
        }
      }
    }

    return record;
  } catch (error) {
    const record = buildReportRecord(sourceItem);
    record.action = "failed";
    record.import_error = "submit_request_failed";
    record.import_message = error instanceof Error ? error.message : String(error);
    return record;
  }
}

async function runSubmit(preparedRows, options) {
  const gatewayRootUrl = resolveGatewayRootUrl(options.baseUrl);
  const resolvedBaseUrl = resolveBaseUrl(options.baseUrl);
  if (!resolvedBaseUrl) {
    throw new Error("submit 模式必须提供 --base-url");
  }
  let accessToken = options.token;
  if (!accessToken) {
    if (!options.email || !options.password) {
      throw new Error("submit 模式必须提供 --token，或提供 --email/--password（也可通过 OPS_ADMIN_EMAIL/OPS_ADMIN_PASSWORD）");
    }
    accessToken = await loginOpsAdmin({
      gatewayRootUrl,
      email: options.email,
      password: options.password,
      timeoutMs: options.timeoutMs,
    });
    console.log(`已使用账号 ${maskEmail(options.email)} 自动获取访问令牌`);
  }

  const items = [];
  const summary = {
    total: preparedRows.length,
    inserted: 0,
    updated: 0,
    skipped: 0,
    duplicate: 0,
    receipt_incomplete: 0,
    failed: 0,
    image_uploaded: 0,
    image_failed: 0,
  };

  const totalCount = preparedRows.length;
  const submitBatches = chunkArray(
    preparedRows.map((sourceItem, itemIndex) => ({ sourceItem, itemIndex })),
    options.submitConcurrency,
  );
  console.log(`submit 将按并发 ${options.submitConcurrency} 执行，共 ${submitBatches.length} 轮。`);

  for (let batchIndex = 0; batchIndex < submitBatches.length; batchIndex += 1) {
    const submitBatch = submitBatches[batchIndex];
    console.log(`开始第 ${batchIndex + 1}/${submitBatches.length} 轮并发提交，共 ${submitBatch.length} 题`);
    const records = await Promise.all(
      submitBatch.map(({ sourceItem, itemIndex }) => submitSingleQuestion({
        sourceItem,
        itemIndex,
        totalCount,
        resolvedBaseUrl,
        accessToken,
        options,
      })),
    );

    records.forEach((record) => {
      updateSummaryByRecord(summary, record);
      if (record.image_uploaded) {
        summary.image_uploaded += 1;
      } else if (record.image_file && record.image_message) {
        summary.image_failed += 1;
      }
      items.push(record);
    });
  }

  return {
    generated_at: new Date().toISOString(),
    command: "submit",
    source_file: options.sourceFilePath,
    summary,
    items,
  };
}

async function main() {
  const { command, filePath, options } = parseArgs(process.argv.slice(2));
  if (command === "template") {
    const outputPath = filePath.toLowerCase().endsWith(".xlsx")
      ? filePath
      : `${filePath}.xlsx`;
    const workbook = buildTemplateWorkbook();
    const content = XLSX.write(workbook, {
      type: "buffer",
      bookType: "xlsx",
    });
    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    await fs.writeFile(outputPath, content);
    console.log(`模板已生成：${outputPath}`);
    return;
  }

  const { rows: sourceRows, sheetDefaults } = await readSourcePayload(filePath);
  const effectiveDefaults = mergeDefaultValues(
    sheetDefaults,
    {
      category: options.defaultCategory,
      sourceUrl: options.defaultSourceUrl,
      announceAt: options.defaultAnnounceAt,
      scheduledPublishAt: options.defaultScheduledPublishAt,
    },
  );
  const { preparedRows, validationErrors } = await buildPreparedRows(
    sourceRows,
    options,
    effectiveDefaults,
  );
  printValidationSummary(preparedRows, validationErrors);

  if (command === "plan") {
    printPlan(preparedRows, effectiveDefaults);
  }

  if (validationErrors.length > 0) {
    process.exitCode = 1;
    return;
  }

  if (command === "validate" || command === "plan") {
    return;
  }

  const report = await runSubmit(preparedRows, {
    ...options,
    sourceFilePath: filePath,
  });
  const reportPaths = await writeReport(options.reportDir, report);

  console.log("导题完成：");
  console.log(`- 插入 ${report.summary.inserted} 条`);
  console.log(`- 更新 ${report.summary.updated} 条`);
  console.log(`- 跳过 ${report.summary.skipped} 条`);
  console.log(`- 重复未提交 ${report.summary.duplicate} 条`);
  console.log(`- 回执不完整 ${report.summary.receipt_incomplete} 条`);
  console.log(`- 失败 ${report.summary.failed} 条`);
  console.log(`- 图片上传成功 ${report.summary.image_uploaded} 条`);
  console.log(`- 图片上传失败 ${report.summary.image_failed} 条`);
  console.log(`- JSON 报告：${reportPaths.jsonPath}`);
  console.log(`- Markdown 报告：${reportPaths.mdPath}`);
}

main().catch((error) => {
  console.error(`执行失败：${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
