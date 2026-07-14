# Validation Profiles

不要默认全读全做。先选画像，再只执行相关 section。

## `base`

所有项目都要做：
- 验证计划文档路径和引用路径存在
- 提取每个 story 的文件、目录、依赖、验收条件
- 对“已有目录 / 已有函数 / 已有调用关系”这类说法，用实际搜索确认
- 对所有显式数字声明，决定是否需要真实计数验证
- 任何写入 `progress.txt` 的模式信息都必须来自真实代码或真实文件

## `data`

只在存在数据文件批量补全、迁移、汇总、条目数声明时执行：
- 用脚本实际读取 YAML / JSON / CSV / 其他结构化文件
- 明确定义“什么算一个条目”
- 递归计数，排除结构节点和 `_meta`
- 检查重复条目和重复 section
- 文档数字与真实数字不一致时，以真实数字为准

不要为了普通 code story 强行做数据递归计数。

## `frontend-code`

只在 story 明显涉及前端组件、交互、i18n、mock、store、design token 时执行：
- i18n 实际模式：确认是 `t('key')` 还是类型化对象访问
- mock 实际能力：确认现有 mock 是否支持 ref、事件、异步行为
- store 模式：确认 setter / action / mutation 方式
- design token / CSS 变量：只记录项目真实存在的 token
- 目录存在性：不存在的目录在 `progress.txt` 标明为“新建”

不要把这些检查强加给纯后端或纯数据计划。

## `backend-code`

只在 story 涉及后端接口、认证、数据库或服务编排时执行：
- route / endpoint 的实际定义位置
- auth / permission / session / middleware 模式
- schema / migration / ORM 约定
- 输入校验和错误处理模式
- 外部服务 mock / fake / fixture 是否已存在

不要复制计划文档中的 API 描述到输出文件；先读真实实现。

## 跳过条件

以下场景可以只执行 `base`：
- 纯 loop 初始化
- 只有 story 编排，没有代码库框架细节
- 用户提供的是高层计划，还没有实际代码目录
