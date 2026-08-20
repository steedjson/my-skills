# SPA 原型爬取 JS 片段

以下结构已在 xiaopiu.com 原型（天玑人事管理系统，8 模块 / 52 页）上验证通过。其他 SPA 先按「探查结构」写选择器，不要硬套。

## 探查结构

```js
// 找候选页面树：li 数 >=3 的 ul
JSON.stringify(
  [...document.querySelectorAll('ul')]
    .map(ul => ({cls: ul.className, li: ul.querySelectorAll(':scope > li').length}))
    .filter(o => o.li >= 3)
    .slice(0, 10)
)
```

```js
// 看全部 li 的 class 分布（判断文件夹层/页面层的标记）
JSON.stringify([...document.querySelectorAll('li')].map(li => li.className).filter(Boolean).slice(0, 40))
```

## xiaopiu 验证结论

- 左侧是 DOM 页面树（非虚拟滚动）：`ul > li` 嵌套；li 内含子 `ul` = 文件夹层，否则 = 页面层。
- 根 li = 项目名，下设 8 个模块文件夹、52 个页面。
- 折叠态 = 子 `ul` 不可见（`offsetParent === null` / `display:none`）。点击该文件夹 li 本身或它的头部元素即可展开。

## 片段（xiaopiu 可直接用）

```js
// 1) 展开所有折叠文件夹（逐个点，间隔 150ms）
JSON.stringify(
  [...document.querySelectorAll('li')].filter(li => {
    const kids = li.querySelector(':scope > ul');
    return kids && kids.offsetParent === null;
  }).map(li => li.click() || (li.innerText || '').trim().split('\n')[0])
)
```

```js
// 2) 枚举全树：D=文件夹 P=页面 d=祖先 ul 层数
// 注意：全局枚举会带出顶部导航（home工作台 等）与登录用户名节点，落 pages.txt 时只保留模块树部分
JSON.stringify([...document.querySelectorAll('li')].map(li => {
  let d = 0, p = li.parentElement;
  while (p && p.tagName === 'UL' && d < 10) { d++; p = p.parentElement; }
  return {
    t: li.querySelector(':scope > ul') ? 'D' : 'P',
    n: (li.innerText || '').trim().split('\n')[0],
    d
  };
}))
```

```js
// 3) 按名称点页面
[...document.querySelectorAll('li')].find(li =>
  !li.querySelector(':scope > ul') &&
  (li.innerText || '').trim().split('\n')[0] === '目标页名'
)?.click()
```

```js
// 4) 每页 sleep 1.2 后提取正文
JSON.stringify({ ok: true, text: document.body.innerText.slice(0, 120000) })
```

```js
// 5) 图片清单（带自然尺寸，供分型：图标/组件条/宽表/照片）
JSON.stringify([...document.images].map(i => ({
  src: i.currentSrc || i.src,
  w: i.naturalWidth,
  h: i.naturalHeight
})))
```

## 页面注册表型 SPA（xiaopiu 原型）

xiaopiu 项目页把全部页面注册在全局对象里，且左侧目录树是懒加载 + 点开后状态会震荡（子节点丢失）。此时**放弃点树**，直接走注册表：

```js
// 1) 枚举全部页面（name + key）
JSON.stringify(window.pages.map((p,i)=>({i, n:p.name, k:p.key})))

// 2) 切页不整刷：goToPage({curr:上一页key, next:目标key, reset:true})
//    sleep 1.2 后取 #page<key> 的 innerText / img 清单

// 3) eval 一律用单个表达式或 IIFE（function(){...}()）
//    顶层 `var x=...;y` 形式偶发 `SyntaxError: missing ) after argument list`
```

已验证：52 页全量文本 + 图片清单 + 整页截图（`goto` 首帧会空 body，用 `screenshot --full` 前须先 `goToPage` 激活目标页）。

## 截图优先模式（原型/UI 清单类任务，首选）

交付物是给人看的 UI/功能清单时，**截图 + 视觉读**优于 DOM 文本爬：画面里布局/分组/步骤条/颜色/徽标一步到位，零 DOM 噪音，截图本身即证据存档。

```bash
# 一循环全页截图（有 window.pages 注册表时）
i=0; prev=0
for k in $(python3 -c "import json;print(' '.join(str(p['k']) for p in json.load(open('pages.json'))))"); do
  agent-browser eval "window.goToPage({curr:$prev,next:$k,reset:true})" >/dev/null
  sleep 1.2
  agent-browser screenshot --full "shots/$(printf %02d $i)_$k.png" >/dev/null
  prev=$k; i=$((i+1))
done
```

- 视觉读分批（每轮 4~8 页），边读边写清单，不必逐页落 DOM 文本。
- DOM 文本/curl JSON 只在需要时回查：精确必填星号、隐藏字段、两版 diff、宽表超视口分段。
- 宽表/长页：viewport 外内容不在截图里 → 读 `naturalWidth`>2500 走 `wide_crop.py`，或用 `--full` 拼长页。

## 通用要点

- 先展开、后枚举、再逐页点击，三步落盘（pages.txt / crawl/NN_名.txt），可断点续爬。
- `chrome_eval` 的 `execute javascript` 支持返回 Promise 并等待，但同步写法最稳；上面的片段都是同步的。
- 点击后固定 `sleep 1.2` 再提取；SPA 路由切换一般 <1s。
- 某页提取为空或明显是上一页残留 → 重新点击该页名再取一次，单独核对页数。
- 宽表截图：读 `naturalWidth`，>2500px 走 `wide_crop.py` 分段。
