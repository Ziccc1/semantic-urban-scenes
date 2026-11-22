# 仓库初始化与协作

## 建仓信息

建议仓库名 semantic-urban-scenes，简介为“四种三维语义城市场景生成方法复现、PrITTI 连续扩展对照与离线可视化”。建议在组长账号或已有课程组织下建私有仓库，默认分支 main。创建空仓库即可使用下面的首次推送流程。拥有相应权限的管理员邀请三位同学加入并授予提交、推分支和开 PR 所需权限。团队若采用课程服务器，可替换下面的 Git 远端地址。

## 首次推送

将起步目录放到单独的项目位置，进入该目录。把 URL 替换成刚创建的空仓库地址。

~~~powershell
git init -b main
git add .
git diff --cached --stat
git commit -m "Initialize project structure and interface docs"
git remote add origin <仓库克隆地址>
git push -u origin main
~~~

若远端已有初始化提交，先克隆远端，再将起步目录中的文件复制进克隆目录，正常提交并推送。初次提交只包含团队文档、目录说明和经过整理的源码或小样例。现有课程目录中的 PDF、PPT、压缩包、数据集和运行输出根据共享需求单独筛选。

## 同学开工

~~~powershell
git clone <仓库克隆地址>
Set-Location semantic-urban-scenes
git switch -c method/pdd-export
~~~

完成一项可检查的工作后提交并推送该分支，发起 PR 合并到 main。共享接口变更由提供方和接收方一起验证。建议首批任务分别为四个方法补运行说明、平台试读已有 PDD 样例、PrITTI 单步扩展导出，以及专项评价表试跑。

## 上传前要补齐的信息

- 四个负责人姓名、代码目录和平台/实验接口的对接人。
- 每条方法的上游仓库、固定版本、依赖、适用设备、数据与权重获取说明、最小运行命令。
- 一个允许组内共享的 PDD 样例及其清单，随后补 PrITTI 单步样例。大型数据和完整日志记共享位置、版本以及获取方式。
- 第三方代码复用方式和授权来源。需要公开发布时，由团队确认课程要求、数据许可及原创代码许可证。
