### Quick Start

1. Install python3 and steamcmd, login to steamcmd and install DST(`app update 343050 validate`)

2. Modify config.yaml to your needs

3. Put save folder in `migrate_dir` in config.yaml

4. Run `python3 dst.py m <cluster_name>` to migrate the cluster

5. Run `python3 dst.py us <cluster_name>` to update and start the game server

### Common Issues

- If you encounter a `DownloadServerMods timed out with no response from Workshop...` error message when downloading mods, try downloading the mod on another computer, then copy the `ugc_mods` in the game folder to the appropriate location on the server. You can refer to this link: [【图片】有关最近饥荒专服不下载MOD的问题【饥荒联机吧】_百度贴吧](https://tieba.baidu.com/p/9251408506)