# 3.6.6 高清四季全景

本文件保留3.6.6历史来源与摘要。当前3.6.8开发批次已替换为hd/368的丰富四季图，见根目录ART368.md和hd/368/provenance.json；旧八张不再随包，可从Git提交737ce912恢复。以下尺寸/哈希为历史记录。

本组替代3.6.5的八张1536×864背景。参考仅为项目自有四季图，OpenAI imagegen扩绘天空/前景，再按4列×2行（裁切相交8px）逐块重绘建筑、树叶、岩石细节；保持季节、昼夜、视角和地标。每块输出原生尺寸均大于最终坐标区域，非直接插值放大旧缩略图。原PNG保留开发工作区，不随包；授权按生成服务条款，未用第三方素材。

坐标合成3840×2880（4:3），低频颜色对齐/相交边缘羽化只消除块间色差，高频保留新绘细节；WebP quality96/method6。取消旧350KiB压缩限制，新图单张预算12MiB，清单预算128MiB。旧独立子夜景预算不变。新hd目录避免低清缓存；全景cover且不用模糊补边；16:9横屏保留全宽地标、裁去新增上下景物，较高平板显示新增天空与前景。用户地点保存键与坐标不改变。

扩绘提示词要点：
> Extend this project-owned xianxia game panorama vertically into a 4:3 composition. Preserve the entire original central panorama and every landmark at exactly its original horizontal position and scale. Paint matching genuine sky above and detailed seasonal rocks, pines and paths below, continuous exquisite traditional fantasy illustration. No stretching, blurred padding, mirrors, people, text, UI or watermark. Keep the supplied season and native day/night lighting.

分区细化提示词要点（逐块附局部参考）：
> Faithfully restore this exact crop of the supplied project-owned fantasy monastery panorama at the highest native portrait detail. Keep the exact camera, proportions, layout, edge continuity, architecture, mountains, trees, season and lighting. Redraw crisp individual roof tiles, carved beams, tiny leaves and rock textures with elegant consistent illustration detail. Do not move, add or remove landmarks; no text, people, UI, border or watermark. This is one overlapping tile of a larger fixed map, so preserve all edge content.

验收以最终WebP实际解码像素/浏览器高DPI绘制倍率为准，不以文件名或单纯放大后的尺寸代替细节检查。美术contact sheet与原生局部检查后，真实页面检查电脑与平板横竖屏、昼夜/季节切换、四边铺满和地点排布。

| 图 | 字节 | SHA256 |
|---|---:|---|
| spring-day | 4425658 | `7ba885c970981236898a11cc852b75afc73eaf7956d15bf18854012382131a5f` |
| spring-night | 4824726 | `434ace3a6b0262dac4dcc8aeb54895f18b5c27d3aff0806162d11eb292de575d` |
| summer-day | 5381888 | `a2173242f8a9d42d5fa5c15ed46be3625c3f7ac652259a9ea51e7930a1b0cba7` |
| summer-night | 5059900 | `a0f1cf89f3e48e075235815abfbcd4c2d80825dc3f605315e105169c45d37246` |
| autumn-day | 4683488 | `11628e1c3bd2ee6a4094b22abf466bb0d520b4ed858cd2ffc63f3231751203ca` |
| autumn-night | 4438276 | `f34937d7a6fcb518e772c8c7697a1184f4d07de3d500bc3fac89d7361f4fe990` |
| winter-day | 4280820 | `e8df4316b2c00f2f183f5d0199237a8518178f5bc71af83e6f6ee6aec49f68a2` |
| winter-night | 4389766 | `57878263ec693256079d1daaf9e2265ea2aa899061a931735c4476751fcc6c58` |

清单去重素材合计：48502250字节。

生成来源（开发工作区ID，不随包原PNG）：

- spring-day：扩绘 `exec-7b2bdf46-1b1b-4764-b0a0-165460cd1f10`；细化 `exec-981cb92e-9b5d-460c-9589-4a0101ca5322`, `exec-dd7cbc4e-b7cb-4d83-b8bc-a2a1c0d4639f`, `exec-51516e1d-0150-4521-9ebb-c9cd319ac799`, `exec-4554cf4b-93a6-4466-bc63-808a5f6c3510`, `exec-49d2d95d-0a0a-409c-a4a1-f13ff0582994`, `exec-bae97966-fdd4-4000-8350-5ec547b909d1`, `exec-8ce96cf2-f514-4d70-a4d5-70e6764ba098`, `exec-59876d7f-44c5-4221-ad8d-14c7829e2758`
- spring-night：扩绘 `exec-3306d50e-75ae-40d3-bd52-ed2a1c7910c5`；细化 `exec-01eaca6b-065b-4339-8a4c-8832197a0722`, `exec-e90113b5-57c4-4b86-b2dd-ee5b8edc3ed1`, `exec-9c4a0628-f85f-4a28-9eed-2ec471bbc55b`, `exec-d5ce9819-ee1b-4d71-ac02-3320811c0674`, `exec-98eae08c-cabc-416f-9a55-8e27893ce331`, `exec-e9f20f93-afe3-41ca-ac62-7c501dad330a`, `exec-4914a660-e439-42a1-b756-5c21c79c02d3`, `exec-bf71b280-9803-445f-b1c2-e8848f8865d8`
- summer-day：扩绘 `exec-17044e4e-3df6-4f34-931a-584209152a13`；细化 `exec-36f79920-78b8-44b5-9630-1488e1fdc08b`, `exec-1dd0a81d-88b7-4773-a9ff-6be9e0a274c2`, `exec-f6fa018d-6b9d-4161-bc1a-97d59f48007e`, `exec-3e7fe564-7f53-4e76-94b5-f2a10d5a43af`, `exec-8511694b-2b93-4685-a530-68364aee6de6`, `exec-78d22440-1e0f-4911-be66-f8948e57653d`, `exec-35d30dc0-ce1d-4a41-9285-112b06dfce6c`, `exec-711a4879-07c4-4990-adf3-189152e010c5`
- summer-night：扩绘 `exec-d7bef61e-e60f-49d7-9746-281ec6c40e02`；细化 `exec-c6eb944f-a007-4bb0-af94-288ecc980234`, `exec-e4a84810-684e-4b81-a994-2c46a010072e`, `exec-a3667345-1acf-434d-bfd9-c2d58cbc4f4f`, `exec-32173fae-b647-47d1-9223-9951e3cc25b0`, `exec-ed769be0-8220-427d-b0c4-23d1b5abddac`, `exec-8ec57355-f1cf-4dc2-951d-95a678ca789e`, `exec-d75a3dac-7356-4bb8-a12d-2afdb06c0250`, `exec-d183b1e5-d8be-4c2a-8906-7c072819cb6c`
- autumn-day：扩绘 `exec-d92b8a31-5981-4a44-a408-8ca19f7bbd0e`；细化 `exec-1df39520-1850-4059-9b78-ab286e1f0359`, `exec-bb86405a-428f-4d84-9a23-605a7ae053df`, `exec-4176ca99-3173-4ba8-a1ee-f32ee69522d7`, `exec-12eb7cf2-9314-4445-81f5-a822822bbec7`, `exec-5f9a4c74-6790-4cac-9d17-83a2eecd906e`, `exec-8a484e48-9c2b-4b3a-9817-1af77aa0d2eb`, `exec-4c13cd90-2c66-4e4f-bf21-2a5d8c2c96b7`, `exec-690f8798-7997-4173-a733-8f351184aeb2`
- autumn-night：扩绘 `exec-fda95a29-2767-4ae5-af65-74af5abfb3f6`；细化 `exec-7975ac83-8e61-473a-915b-005f58f6e14f`, `exec-ef13cefd-bdba-4e4a-a76d-d49d88d4e003`, `exec-d4274168-e7c9-4337-89d5-ee185a88b646`, `exec-c6c41124-e44f-4738-8672-3ad0472fbbef`, `exec-1e87d8df-edfc-477b-a16f-51dd0804f7b2`, `exec-703a5af0-a414-4120-bc17-b6bc4c5a6d84`, `exec-2f9e8fc0-213b-45a3-a61c-b101c62aaf37`, `exec-6a038058-9592-4165-9605-9b229f6dffe8`
- winter-day：扩绘 `exec-39123f31-71e8-49e8-87a3-fe0adcaac4cf`；细化 `exec-c0f1a0d2-b9a4-4c3f-ab8e-865946284d22`, `exec-73b40947-be98-46f8-9600-a35af723ebe3`, `exec-93157ada-7a3d-4d87-bb70-0123b642dccc`, `exec-4ee0fb27-fcd3-4c31-a883-f8a0326d62db`, `exec-22aa7110-5f3b-40de-8f31-2c3f40b10004`, `exec-0679d163-4163-4218-a9da-95b3e956b938`, `exec-88ecad5c-7e74-4182-98f2-226a831d7177`, `exec-062f2492-59c7-4694-8031-68bc7c79ae2d`
- winter-night：扩绘 `exec-8d985696-bc72-41a1-9160-88b86f72dfeb`；细化 `exec-0adc9773-3471-415a-b19a-c43a079db7ce`, `exec-6f0078ff-dfbe-4879-8aec-9bd7a8739138`, `exec-c294bbcc-9a50-46a8-b561-90cfa8714f7e`, `exec-aa3c6b35-99e4-4498-8912-84753e8d15d2`, `exec-39e75b79-966e-4fd7-ab0e-c9eff472eb79`, `exec-750ae9d4-139d-4821-a198-ef1f66fd5d8b`, `exec-9fe8045f-adc2-4b31-a612-148084e38922`, `exec-fa6b378a-507d-4b65-a6fb-75e8c9cfa415`
