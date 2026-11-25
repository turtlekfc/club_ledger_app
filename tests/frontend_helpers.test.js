// 前端純函式測試（frontend/index.html 內嵌的 helper）。
// 直接從 index.html 原始碼抽出函式本體來測，不需要瀏覽器、也不需要打包。
// 執行：node --test tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'index.html'), 'utf8');

function extract(startPattern, endPattern) {
  const start = html.search(startPattern);
  assert.ok(start >= 0, `找不到 ${startPattern}，是不是函式被改名或搬走了？`);
  const rest = html.slice(start);
  const end = rest.search(endPattern);
  assert.ok(end >= 0, `找不到結尾 ${endPattern}`);
  return rest.slice(0, end);
}

// escapeHtml（單行）＋ csvCell ＋ FUND/fundingParts/sumFunding 都在同一段連續區塊內
const code = extract(/function escapeHtml\(/, /\n(?=function (?!escapeHtml|csvCell|fundingParts|sumFunding)\w+\()/);
const { escapeHtml, csvCell, FUND, fundingParts, sumFunding } =
  new Function(`${code}\nreturn { escapeHtml, csvCell, FUND, fundingParts, sumFunding };`)();

const exp = (amount, sub) => ({ type: '支出', amount, fundingSubsidyAmount: sub });

test('csvCell：一般文字加雙引號、內部引號跳脫', () => {
  assert.equal(csvCell('一般文字'), '"一般文字"');
  assert.equal(csvCell('逗號,在內'), '"逗號,在內"');
  assert.equal(csvCell('他說"好"'), '"他說""好"""');
});

test('csvCell：公式開頭字元補單引號', () => {
  for (const s of ['=SUM(A1)', '+1', '-2', '@cmd']) {
    assert.equal(csvCell(s), `"'${s}"`);
  }
});

test('csvCell：數字不加引號也不加單引號（負數不被改壞）、空值變空字串', () => {
  assert.equal(csvCell(1500), '1500');
  assert.equal(csvCell(-20), '-20');
  assert.equal(csvCell(null), '""');
  assert.equal(csvCell(undefined), '""');
});

test('fundingParts：自籌／補助／混合', () => {
  assert.deepEqual(fundingParts(exp(1000, 0)), { sub: 0, self: 1000 });
  assert.deepEqual(fundingParts(exp(1000, 1000)), { sub: 1000, self: 0 });
  assert.deepEqual(fundingParts(exp(1000, 300)), { sub: 300, self: 700 });
});

test('fundingParts：收入、轉帳、null 一律不計', () => {
  assert.deepEqual(fundingParts({ type: '收入', amount: 500 }), { sub: 0, self: 0 });
  assert.deepEqual(fundingParts({ type: '轉帳', amount: 500 }), { sub: 0, self: 0 });
  assert.deepEqual(fundingParts(null), { sub: 0, self: 0 });
});

test('fundingParts：欄位缺漏、超過總額、負值都會校正，補助＋自籌恆等於總額', () => {
  assert.deepEqual(fundingParts({ type: '支出', amount: 1000 }), { sub: 0, self: 1000 });
  assert.deepEqual(fundingParts(exp(1000, 5000)), { sub: 1000, self: 0 });
  assert.deepEqual(fundingParts(exp(1000, -5)), { sub: 0, self: 1000 });
});

test('sumFunding：加總後補助＋自籌＝總支出，收入不計入', () => {
  const list = [exp(1000, 300), exp(200, 0), { type: '收入', amount: 9999 }, exp(500, 500)];
  const s = sumFunding(list);
  assert.deepEqual(s, { sub: 800, self: 900 });
  assert.equal(s.sub + s.self, 1700);
  assert.deepEqual(sumFunding([]), { sub: 0, self: 0 });
});

test('FUND 常數與畫面選項一致', () => {
  assert.deepEqual(Object.values(FUND), ['自籌', '補助', '混合']);
  for (const v of Object.values(FUND)) {
    assert.ok(html.includes(`<option value="${v}"`), `記帳表單缺少資金來源選項 ${v}`);
  }
});

test('escapeHtml：跳脫危險字元', () => {
  assert.equal(escapeHtml('<script>"&\'</script>'), '&lt;script&gt;&quot;&amp;&#39;&lt;/script&gt;');
  assert.equal(escapeHtml(null), '');
});
