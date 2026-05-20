// MGTeam.js - MG团队系统

// ==================== 配置文件 ====================
// 创建团队消耗的货币数量
let CreateTeamCost = 100000
// 货币显示名称
let moneyname = "暮源"
// 是否启用在线时长检测（创建/加入团队需要600分钟在线时长）
let EnablePlaytimeCheck = true
// =================================================

// 主菜单模块

let configFile = null;
let teamData = {};
let messageConfigFile = null;
let messageData = {};
let lastMessageViewTime = {};
let messageCooldowns = {};
let teamActivity = {};
let activityTimer = null;
let fundConsumeConfigFile = null;
let fundConsumeData = {};
let fundLogs = {};
let playerMoneyMonitor = {};
let moneyMonitorTimer = null;

/**
 * 初始化数据文件
 */
function initDataFile() {
    try {
        configFile = new JsonConfigFile("plugins/MGTeam/MGteamdata.json", "{}");
        
        const content = configFile.read();
        teamData = content ? JSON.parse(content) : {};
        
        for (let teamId in teamData) {
            if (!teamData[teamId].hasOwnProperty('funds')) {
                teamData[teamId].funds = 0;
            }
            if (!teamData[teamId].hasOwnProperty('isPublic')) {
                teamData[teamId].isPublic = true;
            }
            if (!teamData[teamId].hasOwnProperty('activity')) {
                teamData[teamId].activity = 0;
            }
            if (!teamData[teamId].hasOwnProperty('allowFriendlyFire') || typeof teamData[teamId].allowFriendlyFire !== 'boolean') {
                teamData[teamId].allowFriendlyFire = true;
            }
        }
        
        log("[MGTeam] 已加载团队数据文件，共有 " + Object.keys(teamData).length + " 个团队");
    } catch (err) {
        log("[MGTeam] 数据文件初始化失败: " + err);
        teamData = {};
    }
}

/**
 * 初始化留言板数据文件
 */
function initMessageFile() {
    try {
        messageConfigFile = new JsonConfigFile("plugins/MGTeam/MGteamdata_messages.json", "{}");
        let content = messageConfigFile.read();
        let fullData = content ? JSON.parse(content) : {};
        
        // 兼容性处理与迁移：如果文件内容不包含 'messages' 键，说明是旧格式
        if (fullData && !fullData.hasOwnProperty('messages')) {
            // 旧格式：整个对象就是 messageData
            messageData = fullData;
            lastMessageViewTime = {};
            
            // 尝试从旧的独立查看记录文件迁移（如果存在）
            try {
                let oldViewFile = new JsonConfigFile("plugins/MGTeam/MGteamdata_message_views.json", "{}");
                let viewContent = oldViewFile.read();
                if (viewContent) {
                    let oldViews = JSON.parse(viewContent);
                    if (Object.keys(oldViews).length > 0) {
                        lastMessageViewTime = oldViews;
                        log("[MGTeam] 已从独立文件迁移玩家查看记录");
                    }
                }
            } catch (e) {
                // 忽略迁移错误
            }
            
            // 立即保存为合并后的新格式
            saveMessageData();
        } else {
            // 新格式：包含 messages 和 views
            messageData = fullData.messages || {};
            lastMessageViewTime = fullData.views || {};
        }
        
        log("[MGTeam] 已加载留言板数据（已合并查看记录）");
    } catch (err) {
        log("[MGTeam] 留言板数据初始化失败: " + err);
        messageData = {};
        lastMessageViewTime = {};
    }
}

/**
 * 保存数据到文件
 */
function saveData() {
    try {
        if (configFile) {
            configFile.write(JSON.stringify(teamData, null, 4));
        }
    } catch (err) {
        log("[MGTeam] 保存数据失败: " + err);
    }
}

/**
 * 保存留言板数据到文件
 */
function saveMessageData() {
    try {
        if (messageConfigFile) {
            let dataToSave = {
                messages: messageData,
                views: lastMessageViewTime
            };
            messageConfigFile.write(JSON.stringify(dataToSave, null, 4));
        }
    } catch (err) {
        log("[MGTeam] 保存留言板数据失败: " + err);
    }
}

/**
 * 生成随机团队ID（4位，字母开头，字母+数字混合）
 */
function generateTeamId() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
    const nums = '0123456789';
    let id = chars.charAt(Math.floor(Math.random() * chars.length));
    const allChars = chars + nums;
    for (let i = 0; i < 3; i++) {
        id += allChars.charAt(Math.floor(Math.random() * allChars.length));
    }
    if (teamData[id]) {
        return generateTeamId();
    }
    return id;
}

/**
 * 检查玩家是否在团队中，返回团队ID或null
 */
function getPlayerTeam(player) {
    const xuid = player.xuid;
    for (let teamId in teamData) {
        const team = teamData[teamId];
        if (team.operators && Array.isArray(team.operators)) {
            for (let op of team.operators) {
                if (op.xuid === xuid) {
                    return teamId;
                }
            }
        }
        if (team.members) {
            for (let member of team.members) {
                if (member.xuid === xuid) {
                    return teamId;
                }
            }
        }
    }
    return null;
}

/**
 * 检查玩家是否是指定团队的管理员
 */
function isTeamOperator(player, teamId) {
    if (!teamData[teamId]) return false;
    if (!teamData[teamId].operators || !Array.isArray(teamData[teamId].operators)) return false;
    return teamData[teamId].operators.some(op => op.xuid === player.xuid);
}

/**
 * 检查玩家是否是任何团队的管理员
 */
function isAnyTeamOperator(player) {
    const xuid = player.xuid;
    for (let teamId in teamData) {
        if (teamData[teamId].operators && Array.isArray(teamData[teamId].operators)) {
            if (teamData[teamId].operators.some(op => op.xuid === xuid)) {
                return true;
            }
        }
    }
    return false;
}

/**
 * 获取玩家计分板分数
 */
function getPlayerScore(player, objectiveName) {
    try {
        const score = player.getScore(objectiveName);
        if (score === undefined || score === null) {
            return null;
        }
        return score;
    } catch (err) {
        log("[MGTeam] 获取计分板分数失败: " + err);
        return null;
    }
}

/**
 * 检查玩家是否满足在线时长要求（600分钟）
 */
function checkPlaytimeRequirement(player) {
    const score = getPlayerScore(player, "playtime");
    if (score == null) {
        return { valid: false, current: 0, required: 600, error: "无法获取在线时长数据" };
    }
    return { 
        valid: score >= 600, 
        current: score, 
        required: 600 
    };
}

/**
 * 获取团队的申请列表
 */
function getTeamApplications(teamId) {
    if (!teamData[teamId]) {
        return [];
    }
    return teamData[teamId].membersapplications || [];
}

/**
 * 检查玩家是否有未处理的申请
 */
function hasPendingApplication(playerXuid) {
    for (let teamId in teamData) {
        const apps = teamData[teamId].membersapplications || [];
        for (let app of apps) {
            if (app.xuid === playerXuid) {
                return teamId;
            }
        }
    }
    return null;
}

/**
 * 添加申请记录
 */
function addApplication(teamId, player) {
    if (!teamData[teamId]) return;
    
    if (!teamData[teamId].membersapplications) {
        teamData[teamId].membersapplications = [];
    }
    
    removePlayerAllApplications(player.xuid);
    
    teamData[teamId].membersapplications.push({
        xuid: player.xuid,
        name: player.realName,
        AppliedAt: new Date().toISOString()
    });
    
    saveData();
}

/**
 * 移除玩家所有申请
 */
function removePlayerAllApplications(playerXuid) {
    for (let teamId in teamData) {
        if (teamData[teamId].membersapplications) {
            teamData[teamId].membersapplications = teamData[teamId].membersapplications.filter(app => app.xuid !== playerXuid);
        }
    }
    saveData();
}

/**
 * 移除特定申请
 */
function removeApplication(teamId, playerXuid) {
    if (!teamData[teamId] || !teamData[teamId].membersapplications) return;
    teamData[teamId].membersapplications = teamData[teamId].membersapplications.filter(app => app.xuid !== playerXuid);
    saveData();
}

/**
 * 获取团队的留言列表（最近10条）
 */
function getTeamMessages(teamId) {
    if (!messageData[teamId]) {
        messageData[teamId] = [];
    }
    return messageData[teamId];
}

/**
 * 检查玩家留言冷却时间
 * 检查玩家是否在10分钟内已经添加过留言
 */
function checkMessageCooldown(teamId, playerXuid) {
    const now = Date.now();
    const cooldownKey = `${teamId}_${playerXuid}`;
    
    if (!messageCooldowns[cooldownKey]) {
        return { canSend: true, remainingTime: 0 };
    }
    
    const lastMessageTime = messageCooldowns[cooldownKey];
    const elapsedTime = now - lastMessageTime;
    const cooldownDuration = 10 * 60 * 1000;
    
    if (elapsedTime < cooldownDuration) {
        const remainingTime = Math.ceil((cooldownDuration - elapsedTime) / 1000);
        return { canSend: false, remainingTime: remainingTime };
    }
    
    return { canSend: true, remainingTime: 0 };
}

/**
 * 设置玩家留言冷却时间
 * 记录玩家最后一次留言时间
 */
function setMessageCooldown(teamId, playerXuid) {
    const cooldownKey = `${teamId}_${playerXuid}`;
    messageCooldowns[cooldownKey] = Date.now();
}

/**
 * 检查玩家是否有未查看的新留言
 * 根据最后查看时间判断是否有新留言
 */
function hasNewMessages(player, teamId) {
    const xuid = player.xuid;
    const playerKey = `${teamId}_${xuid}`;
    
    const lastViewTime = lastMessageViewTime[playerKey] || 0;
    
    const messages = getTeamMessages(teamId);
    if (messages.length === 0) {
        return false;
    }
    
    const latestMessageTime = messages[0].timestamp || 0;
    
    return latestMessageTime > lastViewTime;
}

/**
 * 设置玩家最后查看留言时间
 * 记录玩家查看留言的时间
 */
function setLastMessageViewTime(player, teamId) {
    const xuid = player.xuid;
    const playerKey = `${teamId}_${xuid}`;
    lastMessageViewTime[playerKey] = Date.now();
    saveMessageData();
}

/**
 * 添加留言到团队
 * 添加冷却时间检查
 */
function addTeamMessage(teamId, player, content) {
    if (!teamData[teamId]) return false;
    
    const cooldownCheck = checkMessageCooldown(teamId, player.xuid);
    if (!cooldownCheck.canSend) {
        const minutes = Math.floor(cooldownCheck.remainingTime / 60);
        const seconds = cooldownCheck.remainingTime % 60;
        player.tell(`§c[团队系统] §f请等待冷却时间结束再发送留言！\n§7剩余时间: §f${minutes}分${seconds}秒`);
        return false;
    }
    
    if (!messageData[teamId]) {
        messageData[teamId] = [];
    }
    
    const message = {
        senderXuid: player.xuid,
        senderName: player.realName,
        content: content,
        time: new Date().toISOString(),
        timestamp: Date.now()
    };
    
    messageData[teamId].unshift(message);
    
    if (messageData[teamId].length > 100) {
        messageData[teamId] = messageData[teamId].slice(0, 100);
    }
    
    setMessageCooldown(teamId, player.xuid);
    
    saveMessageData();
    
    // 通知在线成员
    const team = teamData[teamId];
    if (team) {
        const operators = team.operators || [];
        const members = team.members || [];
        const allMemberXuids = [...operators.map(o => o.xuid), ...members.map(m => m.xuid)];
        
        allMemberXuids.forEach(xuid => {
            if (xuid === player.xuid) return; // 不通知发送者本人
            const target = mc.getPlayer(xuid);
            if (target) {
                target.tell(`§b[团队系统] §e团队成员 §f${player.realName} §e发布了新留言：\n§7${content.length > 20 ? content.substring(0, 20) + "..." : content}`);
            }
        });
    }
    
    log("[MGTeam] 玩家 " + player.realName + " 在团队 " + teamId + " 添加了留言");
    return true;
}

mc.listen("onServerStarted", () => {
    initDataFile();
    initMessageFile();
    initFundConsumeFile();

    initMoneyMonitor();

    const cmd = mc.newCommand("tm", "MGteam团队系统主命令", PermType.Any);
    cmd.setAlias("teammate");
    cmd.setEnum("GuiAction", ["gui"]);
    cmd.mandatory("action", ParamType.Enum, "GuiAction", "action");
    cmd.overload(["GuiAction"]);
    cmd.overload([]);
    cmd.setCallback((_cmd, origin, output, results) => {
        if (!origin.player) {
            output.error("§c该命令只能由玩家执行！");
            return false;
        }
        const player = origin.player;
        if (!results.action || results.action === "gui") {
            openMainMenu(player);
            return true;
        }
        return true;
    });
    cmd.setup();
    
    const warpCmd = mc.newCommand("tmtp", "MGteam传送锚点系统", PermType.Any);
    warpCmd.overload([]);
    warpCmd.setCallback((_cmd, origin, output, results) => {
        if (!origin.player) {
            output.error("§c该命令只能由玩家执行！");
            return false;
        }
        const player = origin.player;
        handleWarpCommand(player);
        return true;
    });
    warpCmd.setup();
    
    const tpaCmd = mc.newCommand("tmtpa", "MGteam团队玩家互传", PermType.Any);
    tpaCmd.overload([]);
    tpaCmd.setCallback((_cmd, origin, output, results) => {
        if (!origin.player) {
            output.error("§c该命令只能由玩家执行！");
            return false;
        }
        const player = origin.player;
        handleTpaCommand(player);
        return true;
    });
    tpaCmd.setup();
    
    const syncCmd = mc.newCommand("tmsync", "同步团队数据中的玩家名称", PermType.GameMasters);
    syncCmd.overload([]);
    syncCmd.setCallback((_cmd, origin, output, results) => {
        if (origin.player && !origin.player.isOP()) {
            output.error("§c只有服务器管理员才能执行此命令！");
            return false;
        }
        
        const result = syncTeamDataNames();
        output.success(result.message);
        return true;
    });
    syncCmd.setup();
    
    const mgopCmd = mc.newCommand("mgop", "MGteam团队系统管理员面板", PermType.GameMasters);
    mgopCmd.overload([]);
    mgopCmd.setCallback((_cmd, origin, output, results) => {
        if (origin.player && !origin.player.isOP()) {
            output.error("§c只有服务器管理员才能执行此命令！");
            return false;
        }
        
        openAdminTeamList(origin.player);
        return true;
    });
    mgopCmd.setup();
    
    log("[MGTeam] 团队系统命令 /tm /tmtp /tmtpa /tmsync /mgop 已注册");
    
    mc.listen("onExperienceAdd", (player, exp) => {
        handleExperienceGain(player, exp);
    });
    
    startActivityTimer();
});

function startActivityTimer() {
    activityTimer = setInterval(() => {
        reduceTeamActivity();
    }, 60 * 60 * 1000);
    
    log("[MGTeam] 团队活跃度定时器已启动，每小时减少1点活跃度");
}

function handleExperienceGain(player, exp) {
    try {
        const teamId = getPlayerTeam(player);
        if (!teamId) return;
        
        const team = teamData[teamId];
        if (!team) return;
        
        if (team.activity === undefined) {
            team.activity = 0;
        }
        
        team.activity += 1;
        
        log(`[MGTeam] 玩家 ${player.realName} 获得 ${exp} 经验，团队 ${teamId} 活跃度+1，当前活跃度: ${team.activity}`);
        
        saveData();
        
    } catch (err) {
        log("[MGTeam] 处理玩家获得经验时出错: " + err);
    }
}

function reduceTeamActivity() {
    try {
        let reducedCount = 0;
        let totalTeams = Object.keys(teamData).length;

        for (let teamId in teamData) {
            const team = teamData[teamId];

            if (team.activity === undefined) {
                team.activity = 0;
                continue;
            }

            if (team.activity > 0) {
                let deduction = Math.max(1, Math.ceil(team.activity * 0.01));
                team.activity = Math.max(0, team.activity - deduction);
                reducedCount++;
                log(`[MGTeam] 团队 ${teamId} 活跃度-${deduction}，当前活跃度: ${team.activity}`);
            }
        }

        saveData();

        log(`[MGTeam] 每小时活跃度减少完成，共 ${reducedCount}/${totalTeams} 个团队减少了活跃度`);

    } catch (err) {
        log("[MGTeam] 减少团队活跃度时出错: " + err);
    }
}
/**
 * 添加团队积金流水记录
 * @param {String} teamId - 团队ID
 * @param {Number} change - 变动金额
 * @param {String} reason - 变动原因
 */
function addFundLog(teamId, change, reason) {
    if (!fundLogs[teamId]) {
        fundLogs[teamId] = [];
    }
    
    const logEntry = {
        timestamp: Date.now(),
        time: new Date().toISOString(),
        change: change,
        reason: reason || "未知原因"
    };
    
    fundLogs[teamId].unshift(logEntry);
    
    // 仅保存最近50条记录
    if (fundLogs[teamId].length > 50) {
        fundLogs[teamId] = fundLogs[teamId].slice(0, 50);
    }
    
    saveFundConsumeData();
}

/**
 * 打开团队积金流水菜单
 * @param {Player} player - 玩家对象
 * @param {String} teamId - 团队ID
 */
function openFundLogMenu(player, teamId) {
    const team = teamData[teamId];
    if (!team) return;
    
    const logs = fundLogs[teamId] || [];
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【积金流水】");
    
    let content = "§e团队：§f" + team.name + "\n";
    content += "§e当前积金：§f" + (team.funds || 0) + moneyname + "\n\n";
    
    if (logs.length === 0) {
        content += "§7暂无积金流水记录。";
    } else {
        content += "§e最近50条变动流水：\n\n";
        for (let i = 0; i < logs.length; i++) {
            const entry = logs[i];
            const date = new Date(entry.timestamp);
            const timeStr = `§7[${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}]`;
            const changeStr = entry.change >= 0 ? `§a+${entry.change}` : `§c${entry.change}`;
            content += `${timeStr} ${changeStr}§r §f${entry.reason}\n`;
        }
    }
    
    form.setContent(content);
    form.addButton("§l返回", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        openTeamManageMenu(pl, teamId);
    });
}

function openFundLogMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    if (!team) return;
    
    const logs = fundLogs[teamId] || [];
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【积金流水】§c[OP快捷管理]");
    
    let content = "§c§l[OP快捷管理]§f\n§e团队：§f" + team.name + "\n";
    content += "§e当前积金：§f" + (team.funds || 0) + moneyname + "\n\n";
    
    if (logs.length === 0) {
        content += "§7暂无积金流水记录。";
    } else {
        content += "§e最近50条变动流水：\n\n";
        for (let i = 0; i < logs.length; i++) {
            const entry = logs[i];
            const date = new Date(entry.timestamp);
            const timeStr = `§7[${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}]`;
            const changeStr = entry.change >= 0 ? `§a+${entry.change}` : `§c${entry.change}`;
            content += `${timeStr} ${changeStr}§r §f${entry.reason}\n`;
        }
    }
    
    form.setContent(content);
    form.addButton("§l返回", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        openTeamManageMenuAsAdmin(pl, teamId);
    });
}

function openAdminTeamList(player) {
    const allTeams = [];

    for (let teamId in teamData) {
        const team = teamData[teamId];
        allTeams.push({
            teamId: teamId,
            name: team.name,
            funds: team.funds || 0,
            activity: team.activity || 0,
            memberCount: (team.members ? team.members.length : 0) + (team.operators ? team.operators.length : 0)
        });
    }

    allTeams.sort((a, b) => {
        if (a.activity > 0 && b.activity === 0) return -1;
        if (b.activity > 0 && a.activity === 0) return 1;
        if (a.activity > 0 && b.activity > 0) return b.activity - a.activity;
        return b.funds - a.funds;
    });

    if (allTeams.length === 0) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【OP团队管理】");
        form.setContent("§c当前没有任何团队！");
        form.addButton("§l关闭", "textures/menu_1/lastpage");
        player.sendForm(form);
        return;
    }

    const form = mc.newSimpleForm();
    form.setTitle("§l【OP团队管理】");
    form.setContent("§e排行榜按活跃度与积金综合排序：\n§7共 " + allTeams.length + " 个团队\n\n§7点击团队按钮以管理员身份进入管理");

    for (let i = 0; i < allTeams.length; i++) {
        const team = allTeams[i];
        // 修改：使用 moneyname 变量
        const buttonText = `§l${team.name}\n§r活跃度: §f${team.activity} §1| §r积金: §f${team.funds}${moneyname} §1| §r成员: §f${team.memberCount}人`;
        form.addButton(buttonText, "textures/menu_1/tmset");
    }

    form.addButton("§l关闭", "textures/menu_1/lastpage");


    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === allTeams.length) {
            return;
        }

        if (id >= 0 && id < allTeams.length) {
            const selectedTeam = allTeams[id];
            openMainMenuAsAdmin(pl, selectedTeam.teamId);
        }
    });
}
function openMainMenuAsAdmin(player, teamId) {
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    if (!teamData[teamId]) {
        openAlertMenu(player, `§c团队 ${teamId} 不存在！`, () => {
            openAdminTeamList(player);
        });
        return;
    }
    
    const team = teamData[teamId];
    
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【§r" + team.name + "§r§l】§c[OP快捷管理]");
    
    let noticePreview = "";
    if (team.notice && team.notice.trim() !== "") {
        const formattedNotice = team.notice.replace(/\\n/g, "\n").replace(/\n/g, "\n§f");
        noticePreview = "\n\n§e§l团队公告：\n§r" + formattedNotice;
    }
    
    form.setContent("§c§lOP快捷管理§f\n§e团队：§f" + team.name + "\n§e团队ID：§f" + teamId + "\n§e活跃度：§f" + (team.activity || 0) + noticePreview);
    
    form.addButton("§l详情信息\n§r§t查看团队详情信息", "textures/menu_1/thebook");
    form.addButton("§l传送锚点\n§r§t团队共享传送点", "textures/menu_1/tmtp");
    
    const onlineTeammatesCount = getOnlineTeammatesCount(player, teamId);
    if (onlineTeammatesCount >= 1) {
        form.addButton("§l成员互传\n§r§2当前在线队友：" + onlineTeammatesCount, "textures/menu_1/online");
    } else {
        form.addButton("§l成员互传\n§r§t成员间免同意传送", "textures/menu_1/tmtpa");
    }
    
    const teamFunds = team.funds || 0;
    form.addButton("§l团队积金\n§r§t当前积金：" + teamFunds + moneyname, "textures/menu_1/tmmoney");
    
    if (hasNewMessages(player, teamId)) {
        form.addButton("§l留言板\n§r§2有新的留言，点击查看", "textures/menu_1/newliuyan");
    } else {
        form.addButton("§l留言板\n§r§t查看和发布团队成员留言", "textures/menu_1/liuyanban");
    }
    
    form.addButton("§l管理团队\n§r§t团队管理员专属菜单", "textures/menu_1/tmset");
    form.addButton("§c§l返回管理员面板", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null) {
            openAdminTeamList(pl);
            return;
        }
        
        switch (id) {
            case 0: openTeamDetailAsAdmin(pl, teamId); break;
            case 1: openWarpMainMenuAsAdmin(pl, teamId); break;
            case 2: openTpaMainMenuAsAdmin(pl, teamId); break;
            case 3: openTeamFundMenuAsAdmin(pl, teamId); break;
            case 4: openMessageBoardAsAdmin(pl, teamId); break;
            case 5: openTeamManageMenuAsAdmin(pl, teamId); break;
            case 6: openAdminTeamList(pl); break;
        }
    });
}

function openTeamDetailAsAdmin(player, teamId) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【团队详情信息】§c[OP快捷管理]");
    
    let content = "§c§l[OP快捷管理]§f\n\n";
    content += "§e§l团队：§f" + team.name + "\n";
    content += "§7团队ID：§f" + teamId + "\n";
    content += "\n§e§l团队活跃度：§f" + (team.activity || 0) + "\n";
    
    if (team.notice && team.notice.trim() !== "") {
        const formattedNotice = team.notice.replace(/\\n/g, "\n").replace(/\n/g, "\n§f");
        content += "\n§e§l团队公告：§r\n" + formattedNotice;
    }
    
    content += "\n§e§l团队管理员：\n";
    if (team.operators && Array.isArray(team.operators)) {
        for (let op of team.operators) {
            content += "§f• " + getPlayerDisplayName(op) + "\n";
        }
    }
    content += "\n";
    
    content += "§e§l普通成员：\n";
    if (team.members && Array.isArray(team.members)) {
        if (team.members.length > 0) {
            for (let member of team.members) {
                content += "§f• " + getPlayerDisplayName(member) + "\n";
            }
        } else {
            content += "§7暂无普通成员\n";
        }
    } else {
        content += "§7暂无普通成员\n";
    }
    content += "\n";
    
    let memberCount = 0;
    if (team.members && Array.isArray(team.members)) {
        memberCount = team.members.length;
    }
    let operatorCount = team.operators ? team.operators.length : 0;
    content += "§e§l成员统计：§f" + (memberCount + operatorCount) + "人§7（管理员:" + operatorCount + "人，普通成员:" + memberCount + "人）\n\n";
    
    const teamFunds = team.funds || 0;
    content += "§e§l团队资金：§f" + teamFunds + " §7" + moneyname + "\n\n";
    
    const apps = getTeamApplications(teamId);
    if (apps.length > 0) {
        content += "§e§l待处理申请：§c" + apps.length + "条\n\n";
    }
    
    content += "§7§oMGteam原创团队系统";
    
    form.setContent(content);
    form.addButton("§l返回管理菜单", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        openMainMenuAsAdmin(pl, teamId);
    });
}

function openTeamManageMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const apps = getTeamApplications(teamId);
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【团队管理】§c[OP快捷管理]");
    
    let noticeStatus = "§7未设置";
    if (team.notice && team.notice.trim() !== "") {
        noticeStatus = "§a已设置（" + team.notice.length + "字符）";
    }
    
    let publicStatus = team.isPublic ? "§a公开（可在排行榜中被查找）" : "§c私密";
    let friendlyFireStatus = team.allowFriendlyFire ? "§2已开启" : "§c已关闭";
    
    form.setContent("§c§l[OP快捷管理]§f\n§7团队名称：§f" + team.name + "\n§7团队ID：§f" + teamId + "\n§7团队公告：" + noticeStatus + "\n§7团队公开性：" + publicStatus + "\n§7成员误伤：" + friendlyFireStatus + "\n§7团队活跃度：§f" + (team.activity || 0));
    
    form.addButton("§l管理团队成员\n§r§t设置权限与移除成员", "textures/menu_1/guanliplayer");
    if (apps.length > 0) {
        form.addButton("§l管理加入申请\n§r§c" + apps.length + "§2条新的申请！", "textures/menu_1/xindeshenqing");
    } else {
        form.addButton("§l管理加入申请\n§r§t暂无申请", "textures/menu_1/guanlishenqing");
    }
    
    form.addButton("§l编辑团队公告\n§r§t将展示在团队主菜单与排行榜中", "textures/menu_1/guanligonggao");
    
    form.addButton("§l团队积金流水\n§r§t查看积金变动记录", "textures/menu_1/tmmoney");
    
    form.addButton("§l修改团队名称\n§r§t当前名称：" + team.name, "textures/menu_1/guanligonggao");
    
    if (team.isPublic) {
        form.addButton("§l设置团队公开性\n§r§2当前状态：公开（可在排行榜中被查找）", "textures/menu_1/unlock");
    } else {
        form.addButton("§l设置团队公开性\n§r§t当前状态：私密", "textures/menu_1/lock");
    }
    
    if (team.allowFriendlyFire) {
        form.addButton("§l成员误伤\n§r§c当前状态：开启", "textures/menu_1/unlock");
    } else {
        form.addButton("§l成员误伤\n§r§2当前状态：关闭", "textures/menu_1/lock");
    }
    
    form.addButton("§c§l解散团队", "textures/menu_1/jiesan");
    form.addButton("§l返回管理菜单", "textures/menu_1/lastpage");
    form.addButton("§l返回管理员面板", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null) {
            openMainMenuAsAdmin(pl, teamId);
            return;
        }
        
        switch (id) {
            case 0:
                openManageMembersAsAdmin(pl, teamId);
                break;
            case 1:
                openManageApplicationsAsAdmin(pl, teamId);
                break;
            case 2:
                openNoticeEditMenuAsAdmin(pl, teamId);
                break;
            case 3:
                openFundLogMenuAsAdmin(pl, teamId);
                break;
            case 4:
                openRenameTeamMenuAsAdmin(pl, teamId);
                break;
            case 5:
                toggleTeamPublicStatusAsAdmin(pl, teamId);
                break;
            case 6:
                toggleFriendlyFireStatusAsAdmin(pl, teamId);
                break;
            case 7:
                openDisbandConfirmMenuAsAdmin(pl, teamId);
                break;
            case 8:
                openMainMenuAsAdmin(pl, teamId);
                break;
            case 9:
                openAdminTeamList(pl);
                break;
        }
    });
}

function openMessageBoardAsAdmin(player, teamId) {
    setLastMessageViewTime(player, teamId);
    
    const team = teamData[teamId];
    const messages = getTeamMessages(teamId);
    
    const cooldownCheck = { canSend: true, remainingTime: 0 };
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【留言板】§c[OP快捷管理]");
    
    let content = "§c§l[OP快捷管理]§f\n\n§e团队：§f" + team.name + "\n§e团队活跃度：§f" + (team.activity || 0) + "\n";
    
    if (messages.length === 0) {
        content += "§7还没有留言，快来发布第一条留言吧！\n\n";
    } else {
        const recentMessages = messages.slice(0, 10);
        content += "§e最近留言：§7（共" + messages.length + "条）\n\n";
        
        for (let i = 0; i < recentMessages.length; i++) {
            const msg = recentMessages[i];
            const timeStr = formatMessageTime(msg.time);
            
            content += "§f" + (i + 1) + ". §e" + msg.senderName + " §7(" + timeStr + ")\n";
            content += "   §f" + msg.content + "\n\n";
        }
        
        if (messages.length > 10) {
            content += "§7...还有" + (messages.length - 10) + "条更早的留言\n\n";
        }
    }
    
    content += "§7留言板只保存最近十条留言！";
    
    form.setContent(content);
    
    form.addButton("§2§l添加留言", "textures/menu_1/addliuyan");
    form.addButton("§l返回管理菜单", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null) {
            openMainMenuAsAdmin(pl, teamId);
            return;
        }
        
        if (id === 0) {
            openAddMessageMenuAsAdmin(pl, teamId);
        } else if (id === 1) {
            openMainMenuAsAdmin(pl, teamId);
        }
    });
}

function openAddMessageMenuAsAdmin(player, teamId) {
    const form = mc.newCustomForm();
    form.setTitle("§l【添加留言】§c[OP快捷管理]");
    
    form.addLabel("§c§l[OP快捷管理]§f\n§e发布留言到留言板\n\n§7• 留言内容将在团队中公开可见\n• 请文明发言，尊重他人\n• 每条留言最多200字\n• 管理员不受10分钟冷却限制\n");
    form.addInput("§7留言内容", "我想说的话...", "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openMessageBoardAsAdmin(pl, teamId);
            return;
        }
        
        const messageContent = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        if (!messageContent || messageContent === "") {
            openAlertMenu(pl, "§c留言内容不能为空！", () => {
                openAddMessageMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        if (messageContent.length > 200) {
            openAlertMenu(pl, "§c留言内容过长！\n§7当前：" + messageContent.length + "字\n§7限制：200字", () => {
                openAddMessageMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        if (!messageData[teamId]) {
            messageData[teamId] = [];
        }
        
        const message = {
            senderXuid: pl.xuid,
            senderName: pl.realName + "§c[管理员]",
            content: messageContent,
            time: new Date().toISOString(),
            timestamp: Date.now()
        };
        
        messageData[teamId].unshift(message);
        
        if (messageData[teamId].length > 100) {
            messageData[teamId] = messageData[teamId].slice(0, 100);
        }
        
        saveMessageData();
        
        // 通知在线成员 (OP发布的留言也通知)
        const team = teamData[teamId];
        if (team) {
            const operators = team.operators || [];
            const members = team.members || [];
            const allMemberXuids = [...operators.map(o => o.xuid), ...members.map(m => m.xuid)];
            
            allMemberXuids.forEach(xuid => {
                if (xuid === pl.xuid) return;
                const target = mc.getPlayer(xuid);
                if (target) {
                    target.tell(`§b[团队系统] §e团队管理员 §f${pl.realName} §e发布了新留言：\n§7${messageContent.length > 20 ? messageContent.substring(0, 20) + "..." : messageContent}`);
                }
            });
        }
        
        pl.tell("§a[团队系统] §f留言发布成功！§c[管理员]");
        log("[MGTeam] 管理员 " + pl.realName + " 在团队 " + teamId + " 发布了留言");
        
        setTimeout(() => {
            openMessageBoardAsAdmin(pl, teamId);
        }, 500);
    });
}

function openTeamFundMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const teamFunds = team.funds || 0;
    const teamActivity = team.activity || 0;
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【团队资金】§c[OP快捷管理]");
    form.setContent("§c§l[OP快捷管理]§f\n§e团队资金管理\n\n§e§l团队：§f" + team.name + "\n§e§l团队资金：§f" + teamFunds + " §7"+ moneyname +"\n\n§r§7选择操作：");
    
    form.addButton("§2§l存入资金", "textures/menu_1/addtmmoney");
    form.addButton("§c§l取出资金", "textures/menu_1/gettmmoney");
    form.addButton("§l返回管理菜单", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null) {
            openMainMenuAsAdmin(pl, teamId);
            return;
        }
        
        switch (id) {
            case 0:
                openDepositMenuAsAdmin(pl, teamId);
                break;
            case 1:
                openWithdrawMenuAsAdmin(pl, teamId);
                break;
            case 2:
                openMainMenuAsAdmin(pl, teamId);
                break;
        }
    });
}

function openDepositMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const playerMoney = player.getMoney();
    const teamFunds = team.funds || 0;
    const teamActivity = team.activity || 0;
    
    const form = mc.newCustomForm();
    form.setTitle("§l【存入资金】§c[OP快捷管理]");
    form.addLabel("§c§l[OP快捷管理]§f\n§e存入资金到团队账户\n\n§e§l我的余额：§f" + playerMoney + " §7"+ moneyname +"\n§e§l团队资金：§f" + teamFunds + " §7"+ moneyname +"\n§e§l团队活跃度：§f" + teamActivity);
    form.addInput("§7请输入存入金额（正整数）", "例如：100", "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openTeamFundMenuAsAdmin(pl, teamId);
            return;
        }
        
        const amountStr = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        const validation = validateAmount(amountStr);
        if (!validation.valid) {
            openAlertMenu(pl, validation.message, () => {
                openDepositMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        const amount = validation.value;
        
        const currentMoney = pl.getMoney();
        if (currentMoney < amount) {
            openAlertMenu(pl, "§c你的余额不足！\n\n§7我的余额：§f" + currentMoney + " §7"+ moneyname +"\n§7存入金额：§f" + amount + " §7"+ moneyname +"", () => {
                openDepositMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        executeDepositAsAdmin(pl, teamId, amount);
    });
}

function executeDepositAsAdmin(player, teamId, amount) {
    const team = teamData[teamId];
    
    const success = player.reduceMoney(amount);
    if (!success) {
        openAlertMenu(player, "§c扣除个人资金失败，请重试！", () => {
            openDepositMenuAsAdmin(player, teamId);
        });
        return;
    }
    
    team.funds = (team.funds || 0) + amount;
    
    // 记录流水账
    addFundLog(teamId, amount, `管理员 ${player.realName} 存入`);
    
    saveData();
    
    const currentMoney = player.getMoney();
    player.tell("§a[团队系统] §f成功存入 §e" + amount + " §f"+ moneyname +"到团队资金！§c[管理员]");
    player.tell("§a[团队系统] §f我的余额：§e" + currentMoney + " §f"+ moneyname +"，团队资金：§e" + team.funds + " §f"+ moneyname +"");
    log("[MGTeam] 管理员 " + player.realName + " 存入 " + amount + " "+ moneyname +"到团队 " + teamId);
    
    openTeamFundMenuAsAdmin(player, teamId);
}

function openWithdrawMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const teamFunds = team.funds || 0;
    const teamActivity = team.activity || 0;
    
    const form = mc.newCustomForm();
    form.setTitle("§l【取出资金】§c[OP快捷管理]");
    form.addLabel("§c§l[OP快捷管理]§f\n§e从团队账户取出资金\n\n§e§l团队资金：§f" + teamFunds + " §7"+ moneyname +"\n");
    form.addInput("§7请输入取出金额（正整数）", "例如：100", "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openTeamFundMenuAsAdmin(pl, teamId);
            return;
        }
        
        const amountStr = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        const validation = validateAmount(amountStr);
        if (!validation.valid) {
            openAlertMenu(pl, validation.message, () => {
                openWithdrawMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        const amount = validation.value;
        
        if (teamFunds < amount) {
            openAlertMenu(pl, "§c团队资金不足！\n\n§7团队资金：§f" + teamFunds + " §7"+ moneyname +"\n§7取出金额：§f" + amount + " §7"+ moneyname +"", () => {
                openWithdrawMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        executeWithdrawAsAdmin(pl, teamId, amount);
    });
}

function executeWithdrawAsAdmin(player, teamId, amount) {
    const team = teamData[teamId];
    
    team.funds = (team.funds || 0) - amount;
    
    // 记录流水账
    addFundLog(teamId, -amount, `管理员 ${player.realName} 取出`);
    
    const success = player.addMoney(amount);
    if (!success) {
        team.funds = team.funds + amount;
        // 回滚流水账（或者不记账，直接返回错误）
        // 这里选择直接返回，流水账函数目前没有删除功能，简单处理为不触发流水保存或增加一个回滚日志
        // 实际上 LLSE addMoney 很少失败，这里按原逻辑处理
        openAlertMenu(player, "§c增加个人资金失败，已回滚团队资金，请重试！", () => {
            openWithdrawMenuAsAdmin(player, teamId);
        });
        return;
    }
    
    saveData();
    
    const currentMoney = player.getMoney();
    player.tell("§a[团队系统] §f成功从团队资金取出 §e" + amount + " §f"+ moneyname +"！§c[管理员]");
    player.tell("§a[团队系统] §f我的余额：§e" + currentMoney + " §f"+ moneyname +"，团队资金：§e" + team.funds + " §f"+ moneyname +"");
    log("[MGTeam] 管理员 " + player.realName + " 从团队 " + teamId + " 取出 " + amount + " "+ moneyname +"");
    
    openTeamFundMenuAsAdmin(player, teamId);
}

function openWarpMainMenuAsAdmin(player, teamId) {
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【传送锚点】§c[OP快捷管理]");
    form.setContent("§c§l[OP快捷管理]§f\n§7选择操作：");
    
    form.addButton("§e§l前往传送点", "textures/menu_1/gotohome");
    form.addButton("§2§l添加传送点", "textures/menu_1/addtmhome");
    form.addButton("§c§l移除传送点", "textures/menu_1/removetmhome");
    form.addButton("§l返回管理菜单", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 3) {
            openMainMenuAsAdmin(pl, teamId);
            return;
        }
        
        switch (id) {
            case 0:
                openWarpTeleportMenuAsAdmin(pl, teamId);
                break;
            case 1:
                openAddWarpMenuAsAdmin(pl, teamId);
                break;
            case 2:
                openRemoveWarpMenuAsAdmin(pl, teamId);
                break;
        }
    });
}

function openWarpTeleportMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const warpPoints = team.warpPoints || {};
    const warpNames = Object.keys(warpPoints);
    
    if (warpNames.length === 0) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【传送锚点】§c[OP快捷管理]");
        form.setContent("§c§l[OP快捷管理]§f\n§c当前团队没有设置任何传送点！\n\n§7请先创建传送点。");
        form.addButton("§l返回", "textures/menu_1/lastpage");
        player.sendForm(form, (pl, id, reason) => {
            if (id === 0) {
                openWarpMainMenuAsAdmin(pl, teamId);
            }
        });
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【传送锚点】§c[OP快捷管理]");
    form.setContent("§c§l[OP快捷管理]§f\n§e选择传送点：");
    
    for (let name of warpNames) {
        const wp = warpPoints[name];
        const dimName = getDimName(wp.dim);
        form.addButton("§l" + name + "\n§r" + dimName + " | 创建者:" + getPlayerPlainDisplayName({name: wp.creatorName}), "textures/menu_1/tmtp");
    }
    
    form.addButton("§l返回", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === warpNames.length) {
            openWarpMainMenuAsAdmin(pl, teamId);
            return;
        }
        
        if (id >= 0 && id < warpNames.length) {
            const selectedName = warpNames[id];
            const wp = warpPoints[selectedName];
            teleportToWarpAsAdmin(pl, teamId, selectedName, wp);
        }
    });
}

function teleportToWarpAsAdmin(player, teamId, warpName, warpPoint) {
    const pos = mc.newFloatPos(warpPoint.x, warpPoint.y, warpPoint.z, warpPoint.dim);
    
    if (!pos) {
        openAlertMenu(player, "§c传送点坐标异常，无法传送！", () => {
            openWarpTeleportMenuAsAdmin(player, teamId);
        });
        return;
    }
    
    player.teleport(pos);
    player.tell("§a[传送锚点] §f已传送至 §e" + warpName + " §f！§c[管理员]");
    log("[MGTeam] 管理员 " + player.realName + " 传送至团队 " + teamId + " 的传送点 " + warpName);
}

function openAddWarpMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const warpPoints = team.warpPoints || {};
    
    const form = mc.newCustomForm();
    
    form.setTitle("§l【添加传送点】§c[OP快捷管理]");
    form.addLabel("§c§l[OP快捷管理]§f\n§e添加新的传送锚点\n\n§7将你当前的位置设为传送点，方便团队成员快速传送。");
    form.addInput("§7传送点名称", "例如：基地、矿洞、农场", "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openWarpMainMenuAsAdmin(pl, teamId);
            return;
        }
        
        const warpName = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        if (!warpName || warpName.length < 1 || warpName.length > 10) {
            openAlertMenu(pl, "§c传送点名称必须为1-10个字符！", () => {
                openAddWarpMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        if (warpPoints[warpName]) {
            openAlertMenu(pl, "§c传送点名称 §e" + warpName + " §c已存在，请使用其他名称！", () => {
                openAddWarpMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        const pos = pl.pos;
        const currentPos = {
            x: Math.floor(pos.x),
            y: Math.floor(pos.y),
            z: Math.floor(pos.z),
            dim: getPlayerDimId(pl)
        };
        
        openAddWarpConfirmAsAdmin(pl, teamId, warpName, currentPos);
    });
}

function openAddWarpConfirmAsAdmin(player, teamId, warpName, position) {
    const form = mc.newSimpleForm();
    
    const locationText = "§eX:§f" + position.x + " §eY:§f" + position.y + " §eZ:§f" + position.z + " §e维度:§f" + getDimName(position.dim);
    
    form.setTitle("§l【添加传送点】§c[OP快捷管理]");
    form.setContent("§c§l[OP快捷管理]§f\n§e请确认传送点信息：\n\n" +
        "§e§l名称：§f" + warpName + "\n" +
        "§e§l位置：§f" + locationText + "\n" +
        "§e§l创建者：§f" + player.realName + " §c[管理员]\n\n" +
        "§c确认要创建此传送点？");
    
    form.addButton("§l取消", "textures/menu_1/lastpage");
    form.addButton("§2§l确认创建", "textures/menu_1/addtmhome");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 0) {
            openAddWarpMenuAsAdmin(pl, teamId);
            return;
        }
        
        if (id === 1) {
            executeAddWarpAsAdmin(pl, teamId, warpName, position);
        }
    });
}

function executeAddWarpAsAdmin(player, teamId, warpName, position) {
    const team = teamData[teamId];
    
    if (!team.warpPoints) {
        team.warpPoints = {};
    }
    
    team.warpPoints[warpName] = {
        x: position.x,
        y: position.y,
        z: position.z,
        dim: position.dim,
        creatorXuid: player.xuid,
        creatorName: player.realName + "§c[管理员]",
        createdAt: new Date().toISOString()
    };
    
    saveData();
    
    player.tell("§a[传送锚点] §f成功创建传送点 §e" + warpName + "§f！§c[管理员]");
    log("[MGTeam] 管理员 " + player.realName + " 创建了团队 " + teamId + " 的传送点 " + warpName);
    
    openWarpMainMenuAsAdmin(player, teamId);
}

function openRemoveWarpMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const warpPoints = team.warpPoints || {};
    const warpNames = Object.keys(warpPoints);
    
    if (warpNames.length === 0) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【传送锚点】§c[OP快捷管理]");
        form.setContent("§c§l[OP快捷管理]§f\n§c当前团队没有设置任何传送点！");
        form.addButton("§c§l返回", "textures/menu_1/lastpage");
        player.sendForm(form, (pl, id, reason) => {
            if (id === 0) {
                openWarpMainMenuAsAdmin(pl, teamId);
            }
        });
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【移除传送点】§c[OP快捷管理]");
    form.setContent("§c§l[OP快捷管理]§f\n§e选择要移除的传送点：\n§7§o（管理员可移除所有传送点）");
    
    for (let name of warpNames) {
        const wp = warpPoints[name];
        const dimName = getDimName(wp.dim);
        form.addButton("§l" + name + "\n§r" + dimName + " | 创建者:" + getPlayerPlainDisplayName({name: wp.creatorName}), "textures/menu_1/tmtp");
    }
    
    form.addButton("§l返回", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === warpNames.length) {
            openWarpMainMenuAsAdmin(pl, teamId);
            return;
        }
        
        if (id >= 0 && id < warpNames.length) {
            const selectedWarp = warpNames[id];
            openRemoveWarpConfirmAsAdmin(pl, teamId, selectedWarp, warpPoints[selectedWarp]);
        }
    });
}

function openRemoveWarpConfirmAsAdmin(player, teamId, warpName, warpPoint) {
    const form = mc.newSimpleForm();
    
    const locationText = "§eX:§f" + warpPoint.x + " §eY:§f" + warpPoint.y + " §eZ:§f" + warpPoint.z + " §e维度:§f" + getDimName(warpPoint.dim);
    
    form.setTitle("§l【删除传送点】§c[OP快捷管理]");
    form.setContent("§c§l[OP快捷管理]§f\n§c确定要删除以下传送点？\n\n" +
        "§e§l名称：§f" + warpName + "\n" +
        "§e§l位置：§f" + locationText + "\n" +
        "§e§l创建者：" + getPlayerDisplayName({name: warpPoint.creatorName}) + "\n\n" +
        "§c此操作不可撤销！");
    
    form.addButton("§l取消", "textures/menu_1/lastpage");
    form.addButton("§c§l确认删除", "textures/menu_1/removetmhome");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 0) {
            openRemoveWarpMenuAsAdmin(pl, teamId);
            return;
        }
        
        if (id === 1) {
            executeWarpDeleteAsAdmin(pl, teamId, warpName);
        }
    });
}

function executeWarpDeleteAsAdmin(player, teamId, warpName) {
    const team = teamData[teamId];
    
    if (!team.warpPoints || !team.warpPoints[warpName]) {
        openAlertMenu(player, "§c传送点不存在或已被删除！", () => {
            openRemoveWarpMenuAsAdmin(player, teamId);
        });
        return;
    }
    
    delete team.warpPoints[warpName];
    saveData();
    
    player.tell("§a[传送锚点] §f已成功删除传送点 §e" + warpName + "§f！§c[管理员]");
    log("[MGTeam] 管理员 " + player.realName + " 删除了团队 " + teamId + " 的传送点 " + warpName);
    
    openRemoveWarpMenuAsAdmin(player, teamId);
}

function openTpaMainMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const onlinePlayers = mc.getOnlinePlayers();
    const teamMembers = [];
    
    for (let p of onlinePlayers) {
        if (p.xuid === player.xuid) continue;
        
        const pTeamId = getPlayerTeam(p);
        if (pTeamId === teamId) {
            teamMembers.push(p);
        }
    }
    
    if (teamMembers.length === 0) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【成员互传】§c[OP快捷管理]");
        form.setContent("§c§l[OP快捷管理]§f\n§c当前团队没有其他在线玩家！");
        form.addButton("§l关闭", "textures/menu_1/lastpage");
        player.sendForm(form, (pl, id, reason) => {});
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【成员互传】§c[OP快捷管理]");
    form.setContent("§c§l[OP快捷管理]§f\n§7共 " + teamMembers.length + " 名队友在线。\n§e选择要传送的团队成员：");
    
    const playerDim = getPlayerDimId(player);
    const playerPos = player.pos;
    
    for (let teammate of teamMembers) {
        const name = teammate.realName;
        const teammateDim = getPlayerDimId(teammate);
        const teammatePos = teammate.pos;
        
        let line2 = "";
        if (teammateDim === playerDim) {
            const dx = teammatePos.x - playerPos.x;
            const dy = teammatePos.y - playerPos.y;
            const dz = teammatePos.z - playerPos.z;
            const distance = Math.sqrt(dx * dx + dy * dy + dz * dz).toFixed(1);
            
            const posStr = "X:" + Math.floor(teammatePos.x) + " Y:" + Math.floor(teammatePos.y) + " Z:" + Math.floor(teammatePos.z);
            line2 = posStr + " | 距离:" + distance + "米";
        } else {
            line2 = "§7所在维度:" + getDimName(teammateDim);
        }
        
        form.addButton("§l" + name + "\n§r" + line2, "textures/ui/icon_steve");
    }
    
    form.addButton("§l取消", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === teamMembers.length) {
            return;
        }
        
        if (id >= 0 && id < teamMembers.length) {
            const selectedPlayer = teamMembers[id];
            executeTeamTeleportAsAdmin(pl, teamId, selectedPlayer);
        }
    });
}

function executeTeamTeleportAsAdmin(player, teamId, targetPlayer) {
    const targetDim = getPlayerDimId(targetPlayer);
    const targetPos = targetPlayer.pos;
    
    const currentTargetTeam = getPlayerTeam(targetPlayer);
    if (currentTargetTeam !== teamId) {
        openAlertMenu(player, "§c目标玩家已离开团队，无法传送！", () => {
            openTpaMainMenuAsAdmin(player, teamId);
        });
        return;
    }
    
    const destPos = mc.newFloatPos(targetPos.x, targetPos.y, targetPos.z, targetDim);
    
    if (!destPos) {
        openAlertMenu(player, "§c目标位置异常，无法传送！", () => {
            openTpaMainMenuAsAdmin(player, teamId);
        });
        return;
    }
    
    const success = player.teleport(destPos);
    
    if (success) {
        player.sendToast("§a团队互传", "已传送至队友 §e" + targetPlayer.realName + " §a身边！§c[管理员]");
        player.tell("§a[团队系统] §f已传送至 §e" + targetPlayer.realName + " §f身边！§c[管理员]");
        
        targetPlayer.sendToast("§e团队互传", "队友 §a" + player.realName + " §e传送到了你身边！§c[管理员]");
        
        log("[MGTeam] 管理员 " + player.realName + " 传送至队友 " + targetPlayer.realName + " 身边");
    } else {
        player.tell("§c[团队系统] §f传送失败，请重试！");
    }
}

function openManageMembersAsAdmin(player, teamId) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    const memberList = [];
    
    if (team.operators && Array.isArray(team.operators)) {
        for (let op of team.operators) {
            memberList.push({
                xuid: op.xuid,
                name: op.name,
                type: "operator",
                displayName: "管理员-" + getPlayerPlainDisplayName(op)
            });
        }
    }
    
    if (team.members && Array.isArray(team.members)) {
        for (let member of team.members) {
            memberList.push({
                xuid: member.xuid,
                name: member.name,
                type: "member",
                displayName: "普通成员-" + getPlayerPlainDisplayName(member)
            });
        }
    }
    
    if (memberList.length === 0) {
        openAlertMenu(player, "§c团队成员列表为空！", () => {
            openTeamDetailAsAdmin(player, teamId);
        });
        return;
    }
    
    const form = mc.newCustomForm();
    
    form.setTitle("§l【团队系统】§c[OP快捷管理]");
    form.addLabel("§c§l[OP快捷管理]§f\n§e请在名单中选择成员：");
    
    const displayNames = [];
    for (let m of memberList) {
        displayNames.push(m.displayName);
    }
    
    form.addDropdown("§7选择成员", displayNames);
    form.addLabel("§e请选择操作：");
    form.addDropdown("§7操作类型", ["设置为管理员", "设置为普通成员", "移出团队"]);
    
    player.sendForm(form, (pl, data, reason) => {
        if (!player.isOP()) {
            openAlertMenu(player, "§c您没有管理员权限！", () => {});
            return;
        }
        
        if (!data) {
            openTeamDetailAsAdmin(pl, teamId);
            return;
        }
        
        const selectedIndex = parseInt(data[1]);
        const operationType = parseInt(data[3]);
        
        if (isNaN(selectedIndex) || isNaN(operationType)) {
            openAlertMenu(pl, "§c表单数据异常，请重试！", () => {
                openManageMembersAsAdmin(pl, teamId);
            });
            return;
        }
        
        if (selectedIndex < 0 || selectedIndex >= memberList.length) {
            openAlertMenu(pl, "§c选择的成员无效！", () => {
                openManageMembersAsAdmin(pl, teamId);
            });
            return;
        }
        
        const selectedMember = memberList[selectedIndex];
        
        openMemberOperationConfirmAsAdmin(pl, teamId, selectedMember, operationType);
    });
}

function openMemberOperationConfirmAsAdmin(player, teamId, member, operationType) {
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    const opType = Number(operationType);
    let operationName = "未知操作";
    let confirmColor = "§f";
    
    if (opType === 0) {
        operationName = "设置为管理员";
        confirmColor = "§a";
    } else if (opType === 1) {
        operationName = "设置为普通成员";
        confirmColor = "§e";
    } else if (opType === 2) {
        operationName = "移出团队";
        confirmColor = "§c";
    } else {
        openAlertMenu(player, "§c无效的操作类型: " + operationType, () => {
            openManageMembersAsAdmin(player, teamId);
        });
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【团队系统】§c[OP快捷管理]");
    
    const content = "§c§l[OP快捷管理]§f\n§e请确认操作：\n\n" +
        "§7目标成员：" + getPlayerDisplayName(member) + "\n" +
        "§7当前身份：§f" + (member.type === "operator" ? "管理员" : "普通成员") + "\n" +
        "§7执行操作：§f" + operationName + "\n\n" +
        "§c- 注意：管理员拥有团队内所有权限！包含移除成员、移除传送点，甚至是解散团队！\n";
    
    form.setContent(content);
    
    const confirmButtonText = confirmColor + "§l确认" + operationName;
    
    form.addButton("§l取消", "textures/ui/cancel");
    form.addButton(confirmButtonText, "textures/menu_1/right");
    
    player.sendForm(form, (pl, id, reason) => {
        if (!player.isOP()) {
            openAlertMenu(player, "§c您没有管理员权限！", () => {});
            return;
        }
        
        if (id === null) {
            openManageMembersAsAdmin(pl, teamId);
            return;
        }
        
        if (id === 0) {
            openManageMembersAsAdmin(pl, teamId);
            return;
        }
        
        if (id === 1) {
            executeMemberOperationAsAdmin(pl, teamId, member, opType);
        }
    });
}

function executeMemberOperationAsAdmin(player, teamId, member, operationType) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    const opType = Number(operationType);
    
    if (opType === 0) {
        if (team.members && Array.isArray(team.members)) {
            team.members = team.members.filter(m => m.xuid !== member.xuid);
        }
        if (!team.operators) team.operators = [];
        team.operators.push({
            xuid: member.xuid,
            name: member.name
        });
        player.tell("§a[团队系统] §f已将 §e" + member.name + " §f设置为管理员！§c[管理员]");
        log("[MGTeam] 管理员 " + player.realName + " 将 " + member.name + " 设为管理员");
        
    } else if (opType === 1) {
        if (team.operators && Array.isArray(team.operators)) {
            team.operators = team.operators.filter(m => m.xuid !== member.xuid);
        }
        if (!team.members) team.members = [];
        team.members.push({
            xuid: member.xuid,
            name: member.name
        });
        player.tell("§a[团队系统] §f已将 §e" + member.name + " §f设置为普通成员！§c[管理员]");
        log("[MGTeam] 管理员 " + player.realName + " 将 " + member.name + " 设为普通成员");
        
    } else if (opType === 2) {
        if (member.type === "operator") {
            if (team.operators && Array.isArray(team.operators)) {
                team.operators = team.operators.filter(m => m.xuid !== member.xuid);
            }
        } else {
            if (team.members && Array.isArray(team.members)) {
                team.members = team.members.filter(m => m.xuid !== member.xuid);
            }
        }
        player.tell("§a[团队系统] §f已将 §e" + member.name + " §f移出团队！§c[管理员]");
        log("[MGTeam] 管理员 " + player.realName + " 将 " + member.name + " 移出团队");
        clearFundConsumeData(member.xuid);
        const onlinePlayers = mc.getOnlinePlayers();
        for (let p of onlinePlayers) {
            if (p.xuid === member.xuid) {
                p.tell("§c[团队系统] §f你已被管理员移出团队 §e" + team.name + "§f！");
                break;
            }
        }
        
    } else {
        openAlertMenu(player, "§c无效的操作类型！", () => {
            openManageMembersAsAdmin(player, teamId);
        });
        return;
    }
    
    saveData();
    openManageMembersAsAdmin(player, teamId);
}

function openManageApplicationsAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const apps = getTeamApplications(teamId);
    
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【团队系统】§c[OP快捷管理]");
    
    if (apps.length === 0) {
        form.setContent("§c§l[OP快捷管理]§f\n§7当前没有待处理的入队申请。");
        form.addButton("§l返回", "textures/menu_1/lastpage");
        
        player.sendForm(form, (pl, id, reason) => {
            openTeamManageMenuAsAdmin(pl, teamId);
        });
        return;
    }
    
    form.setContent("§c§l[OP快捷管理]§f\n§e请选择要处理的申请：\n§7共 " + apps.length + " 条待处理申请\n");
    
    for (let i = 0; i < apps.length; i++) {
        const app = apps[i];
        const date = new Date(app.AppliedAt);
        const timeStr = date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate() + " " + date.getHours() + ":" + (date.getMinutes() < 10 ? '0' : '') + date.getMinutes();
        form.addButton(getPlayerPlainDisplayName(app) + "\n§r" + timeStr, "textures/ui/icon_steve");
    }
    
    form.addButton("§l返回", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === apps.length) {
            openTeamManageMenuAsAdmin(pl, teamId);
            return;
        }
        
        openApplicationDetailAsAdmin(pl, teamId, apps[id]);
    });
}

function openApplicationDetailAsAdmin(player, teamId, application) {
    const team = teamData[teamId];
    const form = mc.newSimpleForm();
    
    const date = new Date(application.AppliedAt);
    const timeStr = date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate() + " " + date.getHours() + ":" + (date.getMinutes() < 10 ? '0' : '') + date.getMinutes();
    
    form.setTitle("§l【团队系统】§c[OP快捷管理]");
    
    form.setContent("§c§l[OP快捷管理]§f\n§e申请者信息：\n\n§e§l玩家名称：" + getPlayerDisplayName(application) +
        "\n§e§l玩家XUID：§f" + application.xuid +
        "\n§e§l申请时间：§f" + timeStr + "\n\n§7请选择处理方式：");
    
    form.addButton("§c§l忽略申请", "textures/ui/cancel");
    form.addButton("§2§l通过申请", "textures/menu_1/right");
    form.addButton("§l返回", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 2) {
            openManageApplicationsAsAdmin(pl, teamId);
            return;
        }
        
        if (id === 0) {
            removeApplication(teamId, application.xuid);
            pl.tell("§a[团队系统] §f已忽略 " + getPlayerPlainDisplayName(application) + " §f的入队申请§c[管理员]");
            log("[MGTeam] 管理员 " + pl.realName + " 忽略了 " + (application.name || "未知玩家") + " 的申请");
            openManageApplicationsAsAdmin(pl, teamId);
        } else if (id === 1) {
            approveApplicationAsAdmin(pl, teamId, application);
        }
    });
}

function approveApplicationAsAdmin(player, teamId, application) {
    const team = teamData[teamId];
    
    if (getPlayerTeamByXuid(application.xuid)) {
        player.tell("§c[团队系统] §f该玩家已加入其他团队，无法通过申请！");
        removeApplication(teamId, application.xuid);
        openManageApplicationsAsAdmin(player, teamId);
        return;
    }
    
    if (!team.members) {
        team.members = [];
    }
    
    team.members.push({
        xuid: application.xuid,
        name: application.name
    });
    
    saveData();
    
    removeApplication(teamId, application.xuid);
    
    player.tell("§a[团队系统] §f已通过 §e" + application.name + " §f的入队申请！§c[管理员]");
    log("[MGTeam] 管理员 " + player.realName + " 通过了 " + application.name + " 的申请，加入团队 " + team.name);
    
    const onlinePlayers = mc.getOnlinePlayers();
    for (let p of onlinePlayers) {
        if (p.xuid === application.xuid) {
            p.tell("§a[团队系统] §f你的入队申请已通过管理员批准！欢迎加入 §e" + team.name + "§f！");
            break;
        }
    }
    
    openManageApplicationsAsAdmin(player, teamId);
}

function openNoticeEditMenuAsAdmin(player, teamId, defaultContent = "", isRetry = false) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    let currentNotice = "";
    if (!isRetry && defaultContent === "") {
        currentNotice = team.notice || "";
    } else {
        currentNotice = defaultContent;
    }
    
    const form = mc.newCustomForm();
    form.setTitle("§l【团队公告设置】§c[OP快捷管理]");
    
    let labelText = "§c§l[OP快捷管理]§f\n§e编辑团队公告：\n\n";
    labelText += "§7• 公告会显示在主菜单和团队详情中。\n";
    labelText += "§7• 所有团队成员可见。\n";
    labelText += "§7• 使用颜色代码（如§a绿色§7）更改字体颜色。\n";
    labelText += "§7• 过度使用加粗字体可能使你的文本右侧超出菜单界面。\n";
    labelText += "§7• 使用 §f\\\\n §7换行（反斜杠（转义符）+n）。\n";
    labelText += "§7• 最多200字符。\n";
    
    form.addLabel(labelText);
    form.addInput("§7公告内容", "请输入公告内容...", currentNotice);
    
    player.sendForm(form, (pl, data, reason) => {
        if (!player.isOP()) {
            openAlertMenu(player, "§c您没有管理员权限！", () => {});
            return;
        }
        
        if (!data) {
            openTeamManageMenuAsAdmin(pl, teamId);
            return;
        }
        
        const inputContent = (data[1] !== undefined && data[1] !== null) ? String(data[1]) : "";
        
        if (inputContent.length > 200) {
            openAlertMenu(pl, "§c公告内容过长！\n§7当前：" + inputContent.length + "字符\n§7限制：200字符", () => {
                openNoticeEditMenuAsAdmin(pl, teamId, inputContent, true);
            });
            return;
        }
        
        openNoticeConfirmMenuAsAdmin(pl, teamId, inputContent);
    });
}

function openNoticeConfirmMenuAsAdmin(player, teamId, noticeContent) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    let previewText;
    if (noticeContent.trim() === "") {
        previewText = "§7（无公告）";
    } else {
        previewText = noticeContent.replace(/\\n/g, "\n").replace(/\n/g, "\n§f");
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【公告预览】§c[OP快捷管理]");
    
    let content = "§c§l[OP快捷管理]§f\n§e请确认公告内容：\n\n";
    content += "§e§l所属团队：§f" + team.name + "\n";
    content += "§e§l公告长度：§f" + noticeContent.length + "/200字符\n\n";
    content += "§e§l预览效果：§r\n";
    content += "§f━━━━━━━━━━━━━━\n";
    content += previewText + "\n";
    content += "§f━━━━━━━━━━━━━━\n\n";
    content += "§c确认要保存此公告吗？";
    
    form.setContent(content);
    form.addButton("§l返回修改", "textures/menu_1/lastpage");
    form.addButton("§2§l确认保存", "textures/menu_1/guanligonggao");
    
    player.sendForm(form, (pl, id, reason) => {
        if (!player.isOP()) {
            openAlertMenu(player, "§c您没有管理员权限！", () => {});
            return;
        }
        
        if (id === null) {
            openNoticeEditMenuAsAdmin(pl, teamId, noticeContent, true);
            return;
        }
        
        if (id === 0) {
            openNoticeEditMenuAsAdmin(pl, teamId, noticeContent, true);
        } else if (id === 1) {
            saveTeamNoticeAsAdmin(pl, teamId, noticeContent);
        }
    });
}

function saveTeamNoticeAsAdmin(player, teamId, noticeContent) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    team.notice = noticeContent;
    
    saveData();
    
    if (noticeContent.trim() === "") {
        player.tell("§a[团队系统] §f团队公告已清空！§c[管理员]");
        log("[MGTeam] 管理员 " + player.realName + " 清空了团队 " + teamId + " 的公告");
    } else {
        player.tell("§a[团队系统] §f团队公告已更新！§c[管理员]");
        log("[MGTeam] 管理员 " + player.realName + " 更新了团队 " + teamId + " 的公告");
    }
    
    openTeamManageMenuAsAdmin(player, teamId);
}

function openRenameTeamMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    const form = mc.newCustomForm();
    form.setTitle("§l【修改团队名称】§c[OP快捷管理]");
    
    let labelText = "§c§l[OP快捷管理]§f\n§e修改团队名称：\n\n";
    labelText += "§7• 名称长度必须在2-10个字符之间。\n";
    labelText += "§7• 不能与其他团队重名。\n\n";
    labelText += "§e§l当前团队名称：§f" + team.name;
    
    form.addLabel(labelText);
    form.addInput("§7新团队名称", "输入新的团队名称...", team.name);
    
    player.sendForm(form, (pl, data, reason) => {
        if (!player.isOP()) {
            openAlertMenu(player, "§c您没有管理员权限！", () => {});
            return;
        }
        
        if (!data) {
            openTeamManageMenuAsAdmin(pl, teamId);
            return;
        }
        
        const newName = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        if (!newName || newName.length < 2 || newName.length > 10) {
            openAlertMenu(pl, "§c团队名称必须为2-10个字符！", () => {
                openRenameTeamMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        if (newName === team.name) {
            openAlertMenu(pl, "§c新名称与当前名称相同，无需修改！", () => {
                openRenameTeamMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        for (let id in teamData) {
            if (id !== teamId && teamData[id].name === newName) {
                openAlertMenu(pl, "§c已存在同名团队，请更换名称！", () => {
                    openRenameTeamMenuAsAdmin(pl, teamId);
                });
                return;
            }
        }
        
        openRenameConfirmMenuAsAdmin(pl, teamId, team.name, newName);
    });
}

function openRenameConfirmMenuAsAdmin(player, teamId, oldName, newName) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【修改团队名称确认】§c[OP快捷管理]");
    
    let content = "§c§l[OP快捷管理]§f\n§e请确认修改：\n\n";
    content += "§e§l原团队名称：§f" + oldName + "\n";
    content += "§e§l新团队名称：§f" + newName + "\n\n";
    content += "§c确认修改团队名称？";
    
    form.setContent(content);
    form.addButton("§l返回修改", "textures/menu_1/lastpage");
    form.addButton("§2§l确认修改", "textures/menu_1/guanligonggao");
    
    player.sendForm(form, (pl, id, reason) => {
        if (!player.isOP()) {
            openAlertMenu(player, "§c您没有管理员权限！", () => {});
            return;
        }
        
        if (id === null) {
            openRenameTeamMenuAsAdmin(pl, teamId);
            return;
        }
        
        if (id === 0) {
            openRenameTeamMenuAsAdmin(pl, teamId);
        } else if (id === 1) {
            executeRenameTeamAsAdmin(pl, teamId, oldName, newName);
        }
    });
}

function executeRenameTeamAsAdmin(player, teamId, oldName, newName) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    for (let id in teamData) {
        if (id !== teamId && teamData[id].name === newName) {
            openAlertMenu(player, "§c修改失败，已存在同名团队！", () => {
                openTeamManageMenuAsAdmin(player, teamId);
            });
            return;
        }
    }
    
    const previousName = team.name;
    
    team.name = newName;
    
    saveData();
    
    player.tell("§a[团队系统] §f团队名称已从 §e" + oldName + " §f修改为 §e" + newName + "§f！§c[管理员]");
    log("[MGTeam] 管理员 " + player.realName + " 将团队 " + teamId + " 的名称从 " + previousName + " 修改为 " + newName);
    
    const onlinePlayers = mc.getOnlinePlayers();
    for (let p of onlinePlayers) {
        const pTeamId = getPlayerTeam(p);
        if (pTeamId === teamId && p.xuid !== player.xuid) {
            p.tell("§e[团队系统] §f团队名称已由管理员修改：§e" + oldName + " §f→ §e" + newName);
        }
    }
    
    openTeamManageMenuAsAdmin(player, teamId);
}

function toggleTeamPublicStatusAsAdmin(player, teamId) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    team.isPublic = !team.isPublic;
    saveData();
    
    if (team.isPublic) {
        player.tell("§a[团队系统] §f团队已设为§a公开§f状态，其他玩家可以在排行榜中查找并申请加入！§c[管理员]");
        log("[MGTeam] 管理员 " + player.realName + " 将团队 " + teamId + " 设为公开状态");
    } else {
        player.tell("§a[团队系统] §f团队已设为§c私密§f状态，其他玩家无法在排行榜中查找！§c[管理员]");
        log("[MGTeam] 管理员 " + player.realName + " 将团队 " + teamId + " 设为私密状态");
    }
    
    openTeamManageMenuAsAdmin(player, teamId);
}

function toggleFriendlyFireStatusAsAdmin(player, teamId) {
    const team = teamData[teamId];
    
    if (!player.isOP()) {
        openAlertMenu(player, "§c您没有管理员权限！", () => {});
        return;
    }
    
    team.allowFriendlyFire = !team.allowFriendlyFire;
    saveData();
    
    if (team.allowFriendlyFire) {
        player.tell("§a[团队系统] §f成员误伤已§a开启§f，团队成员可以互相攻击！§c[管理员]");
        log("[MGTeam] 管理员 " + player.realName + " 将团队 " + teamId + " 的成员误伤设为开启状态");
    } else {
        player.tell("§a[团队系统] §f成员误伤已§c关闭§f，团队成员间的攻击将被拦截！§c[管理员]");
        log("[MGTeam] 管理员 " + player.realName + " 将团队 " + teamId + " 的成员误伤设为关闭状态");
    }
    
    openTeamManageMenuAsAdmin(player, teamId);
}

function openDisbandConfirmMenuAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const form = mc.newCustomForm();
    
    form.setTitle("§l【团队系统】§c[OP快捷管理]");
    form.addLabel("§c§l[OP快捷管理]§f\n§c§l你真的要解散团队吗？\n\n§c§l-此操作不可撤销！\n");
    form.addLabel("§7若要解散，请在下方输入团队名称：§f" + team.name);
    form.addInput("§7团队名称确认", "请输入：" + team.name, "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openTeamDetailAsAdmin(pl, teamId);
            return;
        }
        
        const inputName = (data[2] !== undefined && data[2] !== null) ? String(data[2]).trim() : "";
        
        if (inputName !== team.name) {
            openAlertMenu(pl, "§c团队名称输入错误，解散失败！", () => {
                openDisbandConfirmMenuAsAdmin(pl, teamId);
            });
            return;
        }
        
        disbandTeamAsAdmin(pl, teamId);
    });
}

function disbandTeamAsAdmin(player, teamId) {
    const team = teamData[teamId];
    const teamName = team.name;
    
    // 清理所有团队成员的积金消费数据
    if (team.operators && Array.isArray(team.operators)) {
        for (let op of team.operators) {
            clearFundConsumeData(op.xuid);
        }
    }
    if (team.members && Array.isArray(team.members)) {
        for (let member of team.members) {
            clearFundConsumeData(member.xuid);
        }
    }
    
    delete teamData[teamId];
    
    if (messageData[teamId]) {
        delete messageData[teamId];
        saveMessageData();
    }
    
    saveData();
    
    player.tell("§a[团队系统] §f团队 §e" + teamName + " §f已成功解散！§c[管理员]");
    log("[MGTeam] 管理员 " + player.realName + " 解散了团队 " + teamName + " (ID: " + teamId + ")");
    
    openAdminTeamList(player);
}

mc.listen("onJoin", (player) => {
    try {
        const xuid = player.xuid;
        const realName = player.realName;

        if (!xuid || !realName) {
            log("[MGTeam] 玩家进服事件：无法获取XUID或名称");
            return;
        }

        // 留言提醒功能
        const teamId = getPlayerTeam(player);
        if (teamId && hasNewMessages(player, teamId)) {
            // 延迟发送，确保玩家加载完成
            setTimeout(() => {
                const pl = mc.getPlayer(xuid);
                if (pl) {
                    const team = teamData[teamId];
                    const form = mc.newSimpleForm();
                    form.setTitle("§l【新留言提醒】");
                    form.setContent(`§e欢迎回来，§f${pl.realName}§e！\n\n§7在你离线期间，团队 §f${team.name} §7有了新的留言。\n\n§f是否现在查看留言板？`);
                    form.addButton("§l立即查看", "textures/menu_1/liuyanban");
                    form.addButton("§l稍后查看", "textures/menu_1/lastpage");
                    
                    pl.sendForm(form, (targetPl, id, reason) => {
                        if (id === 0) {
                            openMessageBoard(targetPl, teamId);
                        }
                    });
                }
            }, 3000); // 延迟3秒，等待玩家完全进入世界
        }

        // 第一步：同步名称（原有功能）
        let needSave = false;

        for (let teamId in teamData) {
            const team = teamData[teamId];
            let updated = false;

            // 检查管理员列表
            if (team.operators && Array.isArray(team.operators)) {
                for (let op of team.operators) {
                    if (op.xuid === xuid && (!op.name || op.name === null || op.name === "null")) {
                        op.name = realName;
                        updated = true;
                        needSave = true;
                        log("[MGTeam] 自动填充管理员名称：XUID=" + xuid + ", Name=" + realName + ", 团队=" + teamId);
                    }
                }
            }

            // 检查普通成员列表
            if (team.members && Array.isArray(team.members)) {
                for (let member of team.members) {
                    if (member.xuid === xuid && (!member.name || member.name === null || member.name === "null")) {
                        member.name = realName;
                        updated = true;
                        needSave = true;
                        log("[MGTeam] 自动填充成员名称：XUID=" + xuid + ", Name=" + realName + ", 团队=" + teamId);
                    }
                }
            }

            // 检查申请列表
            if (team.membersapplications && Array.isArray(team.membersapplications)) {
                for (let app of team.membersapplications) {
                    if (app.xuid === xuid && (!app.name || app.name === null || app.name === "null")) {
                        app.name = realName;
                        updated = true;
                        needSave = true;
                        log("[MGTeam] 自动填充申请者名称：XUID=" + xuid + ", Name=" + realName + ", 团队=" + teamId);
                    }
                }
            }

            // 检查传送点创建者
            if (team.warpPoints) {
                for (let warpName in team.warpPoints) {
                    const warp = team.warpPoints[warpName];
                    if (warp && warp.creatorXuid === xuid && (!warp.creatorName || warp.creatorName === null || warp.creatorName === "null")) {
                        warp.creatorName = realName;
                        updated = true;
                        needSave = true;
                        log("[MGTeam] 自动填充传送点创建者名称：XUID=" + xuid + ", Name=" + realName + ", 团队=" + teamId);
                    }
                }
            }
        }

        if (needSave) {
            saveData();
            log("[MGTeam] 玩家 " + realName + " 进服，已自动同步团队数据中的名称");
        }

        // 第二步：检测同一团队内的重复出现并自动修复
        const intraTeamFixes = fixIntraTeamDuplicates(xuid);
        if (intraTeamFixes.length > 0) {
            // 有修复，通知玩家
            let fixMessage = "§e§l[团队系统] §f检测到您的数据异常，已自动修复：\n";
            for (let fix of intraTeamFixes) {
                fixMessage += "§7• 团队 §f" + fix.teamName + " §7: " + fix.message + "\n";
            }
            player.tell(fixMessage);
            
            // 延迟后检测是否需要处理跨团队重复
            setTimeout(() => {
                checkAndHandleInterTeamDuplicates(player, xuid);
            }, 2000);
        } else {
            // 没有团队内重复，直接检测跨团队重复
            checkAndHandleInterTeamDuplicates(player, xuid);
        }

    } catch (err) {
        log("[MGTeam] 玩家进服处理时出错: " + err);
    }
});

mc.listen("onMobHurt", (mob, source, damage, cause) => {
    try {
        if (!mob || !source) {
            return true;
        }
        
        if (!mob.isPlayer() || !source.isPlayer()) {
            return true;
        }
        
        let targetName = mob.realName || mob.name;
        let attackerName = source.realName || source.name;
        
        if (!targetName || !attackerName) {
            return true;
        }
        
        const targetTeamId = getPlayerTeamByName(targetName);
        const attackerTeamId = getPlayerTeamByName(attackerName);
        
        if (!targetTeamId || !attackerTeamId || targetTeamId !== attackerTeamId) {
            return true;
        }
        
        const team = teamData[targetTeamId];
        
        if (team && team.allowFriendlyFire === false) {
            return false;
        }
        
        return true;
    } catch (e) {
        log("[MGTeam] 处理受伤事件时出错: " + e);
        return true;
    }
});
/**
 * 修复同一团队内的重复出现（同一玩家在同一团队的管理员或成员列表中出现多次）
 * @param {String} xuid - 玩家XUID
 * @returns {Array} 修复记录列表
 */
function fixIntraTeamDuplicates(xuid) {
    const fixes = [];
    
    for (let teamId in teamData) {
        const team = teamData[teamId];
        let teamFixed = false;
        let fixMessage = "";
        
        // 检查管理员列表内的重复
        if (team.operators && Array.isArray(team.operators)) {
            const opOccurrences = [];
            for (let i = 0; i < team.operators.length; i++) {
                if (team.operators[i].xuid === xuid) {
                    opOccurrences.push(i);
                }
            }
            
            // 如果管理员列表中出现多次，保留第一个，删除其余的
            if (opOccurrences.length > 1) {
                // 从后往前删除，避免索引变化
                for (let i = opOccurrences.length - 1; i > 0; i--) {
                    team.operators.splice(opOccurrences[i], 1);
                }
                fixMessage += "管理员列表重复×" + opOccurrences.length + "→1 ";
                teamFixed = true;
                log("[MGTeam] 修复团队 " + teamId + " 的管理员列表重复：玩家 " + xuid + " 出现 " + opOccurrences.length + " 次，已保留1个");
            }
        }
        
        // 检查普通成员列表内的重复
        if (team.members && Array.isArray(team.members)) {
            const memOccurrences = [];
            for (let i = 0; i < team.members.length; i++) {
                if (team.members[i].xuid === xuid) {
                    memOccurrences.push(i);
                }
            }
            
            // 如果成员列表中出现多次，保留第一个，删除其余的
            if (memOccurrences.length > 1) {
                // 从后往前删除，避免索引变化
                for (let i = memOccurrences.length - 1; i > 0; i--) {
                    team.members.splice(memOccurrences[i], 1);
                }
                fixMessage += "成员列表重复×" + memOccurrences.length + "→1 ";
                teamFixed = true;
                log("[MGTeam] 修复团队 " + teamId + " 的成员列表重复：玩家 " + xuid + " 出现 " + memOccurrences.length + " 次，已保留1个");
            }
        }
        
        // 检查既在管理员又在普通成员列表的情况
        const inOperators = team.operators && team.operators.some(op => op.xuid === xuid);
        const inMembers = team.members && team.members.some(mem => mem.xuid === xuid);
        
        if (inOperators && inMembers) {
            // 从普通成员列表中移除，保留管理员身份
            team.members = team.members.filter(mem => mem.xuid !== xuid);
            fixMessage += "双身份冲突（保留管理员）";
            teamFixed = true;
            log("[MGTeam] 修复团队 " + teamId + " 的双身份冲突：玩家 " + xuid + " 同时是管理员和成员，已保留管理员身份");
        }
        
        if (teamFixed) {
            fixes.push({
                teamId: teamId,
                teamName: team.name,
                message: fixMessage.trim()
            });
        }
    }
    
    // 如果有修复，保存数据
    if (fixes.length > 0) {
        saveData();
        log("[MGTeam] 完成 " + fixes.length + " 个团队的数据修复");
    }
    
    return fixes;
}
/**
 * 检测并处理跨团队重复（玩家出现在多个团队中）
 */
function checkAndHandleInterTeamDuplicates(player, xuid) {
    // 检测是否重复加入多个团队
    const duplicateRecords = getPlayerAllTeamRecords(xuid);

    if (duplicateRecords.length > 1) {
        // 发现重复，强制弹出选择界面
        log("[MGTeam] 警告：玩家 " + player.realName + " (XUID: " + xuid + ") 同时存在于 " + duplicateRecords.length + " 个团队中");
        player.tell("§c§l[系统警告] §f检测到您的账号数据异常，请立即处理！");

        // 延迟一点发送表单，确保玩家完全进服
        setTimeout(() => {
            openDuplicateTeamSelector(player, duplicateRecords);
        }, 1000);
    }
}

/**
 * 打开重复团队选择界面（强制选择，不选择一直弹窗）
 */
function openDuplicateTeamSelector(player, records, isRetry = false) {
    if (!isRetry) {
        player.tell("§c§l您同时存在于多个团队中，必须选择一个保留！");
    }

    const form = mc.newSimpleForm();
    form.setTitle("§c§l【系统警告】数据异常处理");

    // 构建警告内容
    let content = "§c§l检测到您的账号同时存在于多个团队中！\n\n";
    content += "§e这是数据异常，您必须选择保留其中一个团队的数据。\n";
    content += "§c选择后，其他团队中的您的数据将被永久删除！\n\n";
    content += "§e§l您当前所在的团队：\n\n";

    for (let i = 0; i < records.length; i++) {
        const record = records[i];
        content += "§f" + (i + 1) + ". §e" + record.teamName + "\n";
        content += "   §7团队ID: " + record.teamId + "\n";
        content += "   §7身份: " + record.roleName + "\n\n";
    }

    content += "§c§l请谨慎选择，此操作不可撤销！";

    form.setContent(content);

    // 为每个团队添加选择按钮
    for (let record of records) {
        const buttonText = "§e保留在 §f" + record.teamName + "\n§7(" + record.roleName + ")";
        form.addButton(buttonText, record.role === "operator" ? "textures/ui/icon_setting" : "textures/ui/icon_steve");
    }

    player.sendForm(form, (pl, id, reason) => {
        // 如果没有做出有效选择（关闭表单或点击无效），重新发送
        if (id === null || id === undefined || id < 0 || id >= records.length) {
            pl.tell("§c§l您必须做出选择！请重新选择要保留的团队。");
            // 延迟后重新发送
            setTimeout(() => {
                openDuplicateTeamSelector(pl, records, true);
            }, 500);
            return;
        }

        // 选择了有效的团队，进入二次确认
        const selectedRecord = records[id];
        openDuplicateConfirmMenu(pl, records, selectedRecord);
    });
}

/**
 * 打开二次确认菜单
 */
function openDuplicateConfirmMenu(player, allRecords, selectedRecord) {
    const otherTeams = allRecords.filter(r => r.teamId !== selectedRecord.teamId);
    
    const form = mc.newSimpleForm();
    form.setTitle("§c§l【最终确认】数据清理");
    
    let content = "§e§l请确认您的选择：\n\n";
    content += "§a§l保留的团队：§f" + selectedRecord.teamName + "\n";
    content += "§a§l保留的身份：§f" + selectedRecord.roleName + "\n\n";
    
    content += "§c§l将被删除的团队数据：\n";
    for (let team of otherTeams) {
        content += "§f• §e" + team.teamName + " §7(" + team.roleName + ")\n";
    }
    
    content += "\n§c§l警告：此操作不可撤销！\n";
    content += "§c删除后您将失去在其他团队中的所有数据和权限！\n\n";
    content += "§e确认要执行此操作吗？";
    
    form.setContent(content);
    form.addButton("§c§l重新选择", "textures/ui/icon_arrow_left");
    form.addButton("§4§l确认删除其他数据", "textures/ui/icon_trash");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === undefined) {
            pl.tell("§c§l您必须做出选择！");
            setTimeout(() => {
                openDuplicateConfirmMenu(pl, allRecords, selectedRecord);
            }, 500);
            return;
        }
        
        if (id === 0) {
            openDuplicateTeamSelector(pl, allRecords, true);
        } else if (id === 1) {
            executeDuplicateCleanup(pl, allRecords, selectedRecord);
        } else {
            setTimeout(() => {
                openDuplicateConfirmMenu(pl, allRecords, selectedRecord);
            }, 500);
        }
    });
}

/**
 * 执行重复数据清理
 */
function executeDuplicateCleanup(player, allRecords, keepRecord) {
    try {
        const xuid = player.xuid;
        let deletedCount = 0;
        
        log("[MGTeam] 玩家 " + player.realName + " 选择保留团队 " + keepRecord.teamId + "，开始清理其他团队数据...");
        
        for (let record of allRecords) {
            if (record.teamId === keepRecord.teamId) continue;
            
            const success = removePlayerFromTeam(xuid, record.teamId, record.role);
            if (success) {
                deletedCount++;
                log("[MGTeam] 已从团队 " + record.teamId + " 中移除玩家 " + player.realName + " (原身份: " + record.roleName + ")");
                
                notifyTeamAdmin(record.teamId, "§e[团队系统] §f玩家 " + (record.data.name || player.realName) + " §f已退出团队（数据清理）");
            }
        }
        
        saveData();
        
        player.tell("§a§l[系统] §f数据清理完成！");
        player.tell("§a已保留团队：§e" + keepRecord.teamName + " §7(" + keepRecord.roleName + ")");
        player.tell("§c已清理团队数：§e" + deletedCount + "个");
        
        log("[MGTeam] 玩家 " + player.realName + " 的重复团队数据清理完成，保留了 " + keepRecord.teamId + "，清理了 " + deletedCount + " 个团队");
        
        setTimeout(() => {
            openMainMenu(player);
        }, 1000);
        
    } catch (err) {
        log("[MGTeam] 执行重复数据清理时出错: " + err);
        player.tell("§c§l[系统错误] §f清理过程中出现错误，请联系管理员！");
    }
}

/**
 * 通知团队管理员（辅助函数）
 */
function notifyTeamAdmin(teamId, message) {
    const team = teamData[teamId];
    if (!team || !team.operators) return;
    
    const onlinePlayers = mc.getOnlinePlayers();
    for (let op of team.operators) {
        for (let pl of onlinePlayers) {
            if (pl.xuid === op.xuid) {
                pl.tell(message);
                break;
            }
        }
    }
}

/**
 * 获取玩家在所有团队中的记录
 * @param {String} xuid - 玩家XUID
 * @returns {Array} 包含该玩家的所有团队记录
 */
function getPlayerAllTeamRecords(xuid) {
    const records = [];
    
    for (let teamId in teamData) {
        const team = teamData[teamId];
        
        if (team.operators && Array.isArray(team.operators)) {
            for (let i = 0; i < team.operators.length; i++) {
                if (team.operators[i].xuid === xuid) {
                    records.push({
                        teamId: teamId,
                        teamName: team.name,
                        role: "operator",
                        roleName: "管理员",
                        index: i,
                        data: team.operators[i]
                    });
                }
            }
        }
        
        if (team.members && Array.isArray(team.members)) {
            for (let i = 0; i < team.members.length; i++) {
                if (team.members[i].xuid === xuid) {
                    records.push({
                        teamId: teamId,
                        teamName: team.name,
                        role: "member",
                        roleName: "普通成员",
                        index: i,
                        data: team.members[i]
                    });
                }
            }
        }
    }
    
    return records;
}

/**
 * 从指定团队中移除玩家（增强版，支持清理时的特殊处理）
 * @param {String} xuid - 玩家XUID
 * @param {String} teamId - 团队ID
 * @param {String} role - 角色类型（operator/member）
 * @returns {Boolean} 是否成功移除
 */
function removePlayerFromTeam(xuid, teamId, role) {
    const team = teamData[teamId];
    if (!team) return false;
    
    let removed = false;
    
    if (role === "operator" && team.operators && Array.isArray(team.operators)) {
        const originalLength = team.operators.length;
        team.operators = team.operators.filter(op => op.xuid !== xuid);
        removed = team.operators.length < originalLength;
    } else if (role === "member" && team.members && Array.isArray(team.members)) {
        const originalLength = team.members.length;
        team.members = team.members.filter(member => member.xuid !== xuid);
        removed = team.members.length < originalLength;
    }
    
    const opCount = team.operators ? team.operators.length : 0;
    const memCount = team.members ? team.members.length : 0;
    if (opCount === 0 && memCount === 0) {
        log("[MGTeam] 团队 " + teamId + " 已无成员，建议手动清理");
    }
    
    return removed;
}

/**
 * 同步团队数据中的玩家名称
 * 遍历所有name为null的项目，使用XUID查询并修复
 */
function syncTeamDataNames() {
    let fixedCount = 0;
    let failedCount = 0;
    let skippedCount = 0;
    const failedXuids = [];
    
    log("[MGTeam] 开始同步团队数据中的玩家名称...");
    
    for (let teamId in teamData) {
        const team = teamData[teamId];
        
        if (team.operators && Array.isArray(team.operators)) {
            for (let op of team.operators) {
                if (!op.name || op.name === null || op.name === "null") {
                    const queriedName = data.xuid2name(op.xuid);
                    if (queriedName && queriedName !== null) {
                        op.name = queriedName;
                        fixedCount++;
                        log("[MGTeam] 已修复管理员名称：XUID=" + op.xuid + ", Name=" + queriedName);
                    } else {
                        failedCount++;
                        failedXuids.push(op.xuid);
                        log("[MGTeam] 无法查询到管理员名称：XUID=" + op.xuid);
                    }
                } else {
                    skippedCount++;
                }
            }
        }
        
        if (team.members && Array.isArray(team.members)) {
            for (let member of team.members) {
                if (!member.name || member.name === null || member.name === "null") {
                    const queriedName = data.xuid2name(member.xuid);
                    if (queriedName && queriedName !== null) {
                        member.name = queriedName;
                        fixedCount++;
                        log("[MGTeam] 已修复成员名称：XUID=" + member.xuid + ", Name=" + queriedName);
                    } else {
                        failedCount++;
                        failedXuids.push(member.xuid);
                        log("[MGTeam] 无法查询到成员名称：XUID=" + member.xuid);
                    }
                } else {
                    skippedCount++;
                }
            }
        }
        
        if (team.membersapplications && Array.isArray(team.membersapplications)) {
            for (let app of team.membersapplications) {
                if (!app.name || app.name === null || app.name === "null") {
                    const queriedName = data.xuid2name(app.xuid);
                    if (queriedName && queriedName !== null) {
                        app.name = queriedName;
                        fixedCount++;
                        log("[MGTeam] 已修复申请者名称：XUID=" + app.xuid + ", Name=" + queriedName);
                    } else {
                        failedCount++;
                        failedXuids.push(app.xuid);
                        log("[MGTeam] 无法查询到申请者名称：XUID=" + app.xuid);
                    }
                } else {
                    skippedCount++;
                }
            }
        }
        
        if (team.warpPoints) {
            for (let warpName in team.warpPoints) {
                const warp = team.warpPoints[warpName];
                if (warp && (!warp.creatorName || warp.creatorName === null || warp.creatorName === "null")) {
                    const queriedName = data.xuid2name(warp.creatorXuid);
                    if (queriedName && queriedName !== null) {
                        warp.creatorName = queriedName;
                        fixedCount++;
                        log("[MGTeam] 已修复传送点创建者名称：XUID=" + warp.creatorXuid + ", Name=" + queriedName);
                    } else {
                        failedCount++;
                        failedXuids.push(warp.creatorXuid);
                        log("[MGTeam] 无法查询到传送点创建者名称：XUID=" + warp.creatorXuid);
                    }
                }
            }
        }
    }
    
    if (fixedCount > 0) {
        saveData();
        log("[MGTeam] 名称同步完成，已保存数据");
    }
    
    const message = "§a团队数据名称同步完成！\n" +
        "§7成功修复：§f" + fixedCount + " 个\n" +
        "§7查询失败：§f" + failedCount + " 个\n" +
        "§7跳过（已有名称）：§f" + skippedCount + " 个";
    
    return {
        success: true,
        message: message,
        fixedCount: fixedCount,
        failedCount: failedCount,
        failedXuids: failedXuids
    };
}

/**
 * 获取玩家显示名称（适配null情况）
 */
function getPlayerDisplayName(playerData) {
    if (!playerData) return "§7（未知玩家）";
    if (!playerData.name || playerData.name === null || playerData.name === "null") {
        return "§7（该玩家长期未上线，无法显示名称）";
    }
    return "§f" + playerData.name;
}

/**
 * 获取纯文本显示名称（不带颜色代码，用于按钮等）
 */
function getPlayerPlainDisplayName(playerData) {
    if (!playerData) return "（未知玩家）";
    if (!playerData.name || playerData.name === null || playerData.name === "null") {
        return "（该玩家长期未上线，无法显示名称）";
    }
    return playerData.name;
}

/**
 * 格式化时间显示
 */
function formatMessageTime(isoTime) {
    try {
        const date = new Date(isoTime);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffMins < 1) {
            return "刚刚";
        } else if (diffMins < 60) {
            return diffMins + "分钟前";
        } else if (diffHours < 24) {
            return diffHours + "小时前";
        } else if (diffDays < 7) {
            return diffDays + "天前";
        } else {
            return date.getMonth() + 1 + "月" + date.getDate() + "日 " + 
                   date.getHours().toString().padStart(2, '0') + ":" + 
                   date.getMinutes().toString().padStart(2, '0');
        }
    } catch (e) {
        return "未知时间";
    }
}

/**
 * 打开团队系统主菜单（修改后：添加留言板按钮，并根据新留言状态显示不同按钮）
 * 1：成员互传按钮根据在线队友数量动态显示
 * 2：团队资金按钮动态显示团队资金余额
 * 3：管理团队与退出团队按钮位置调换
 */
/**
 * 打开团队系统主菜单（修改后：使用 moneyname 变量）
 */
function openMainMenu(player) {
    const teamId = getPlayerTeam(player);
    
    const form = mc.newSimpleForm();
    
    if (teamId) {
        const team = teamData[teamId];
        form.setTitle("§l【§r" + team.name + "§r§l】");
    } else {
        form.setTitle("§l【团队系统】");
    }
    
    if (teamId) {
        const team = teamData[teamId];
        const isOperator = isTeamOperator(player, teamId);
        
        let noticePreview = "";
        if (team.notice && team.notice.trim() !== "") {
            const formattedNotice = team.notice.replace(/\\n/g, "\n").replace(/\n/g, "\n§f");
            noticePreview = "\n\n§e§l团队公告：\n§r" + formattedNotice;
        }
        
        form.setContent("§e欢迎回来，§f" + player.realName + "§e！§f"+"§r§e这里是§r"+ team.name +"§e。§f"+noticePreview);
        
        form.addButton("§l详情信息\n§r§t查看团队详情信息", "textures/menu_1/thebook");
        form.addButton("§l传送锚点\n§r§t团队共享传送点", "textures/menu_1/tmtp");
        
        const onlineTeammatesCount = getOnlineTeammatesCount(player, teamId);
        if (onlineTeammatesCount >= 1) {
            form.addButton("§l成员互传\n§r§2当前在线队友：" + onlineTeammatesCount, "textures/menu_1/online");
        } else {
            form.addButton("§l成员互传\n§r§t成员间免同意传送", "textures/menu_1/tmtpa");
        }
        
        const teamFunds = team.funds || 0;
        // 修改：使用 moneyname 变量
        form.addButton("§l团队积金\n§r§t当前积金：" + teamFunds + moneyname, "textures/menu_1/tmmoney");
        
        if (hasNewMessages(player, teamId)) {
            form.addButton("§l留言板\n§r§2有新的留言，点击查看", "textures/menu_1/newliuyan");
        } else {
            form.addButton("§l留言板\n§r§t查看和发布团队成员留言", "textures/menu_1/liuyanban");
        }
        
        if (isOperator) {
            form.addButton("§l管理团队\n§r§t团队管理员专属菜单", "textures/menu_1/tmset");
            form.addButton("§c§l退出团队", "textures/menu_1/jiesan");
        } else {
            form.addButton("§c§l退出团队", "textures/menu_1/jiesan");
        }
    } else {
        form.setContent("§c你当前未加入任何团队。\n\n§7选择功能：");
        form.addButton("§l创建新团队", "textures/menu_1/tmtpa");
        form.addButton("§l通过ID搜索团队", "textures/menu_1/guanlishenqing");
        form.addButton("§l在排行榜中查找公开团队", "textures/menu_1/findtm");
    }
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null) {
            pl.tell("§7[团队系统] §f已关闭菜单");
            return;
        }
        
        if (teamId) {
            const isOperator = isTeamOperator(pl, teamId);
            if (isOperator) {
                switch (id) {
                    case 0: openTeamDetail(pl, teamId); break;
                    case 1: openWarpMainMenu(pl, teamId); break;
                    case 2: openTpaMainMenu(pl, teamId); break;
                    case 3: openTeamFundMenu(pl, teamId); break;
                    case 4: openMessageBoard(pl, teamId); break;
                    case 5: openTeamManageMenu(pl, teamId); break;
                    case 6: handleQuitTeam(pl, teamId); break;
                }
            } else {
                switch (id) {
                    case 0: openTeamDetail(pl, teamId); break;
                    case 1: openWarpMainMenu(pl, teamId); break;
                    case 2: openTpaMainMenu(pl, teamId); break;
                    case 3: openTeamFundMenu(pl, teamId); break;
                    case 4: openMessageBoard(pl, teamId); break;
                    case 5: handleQuitTeam(pl, teamId); break;
                }
            }
        } else {
            switch (id) {
                case 0: openCreateTeamCheck(pl); break;
                case 1: openJoinByIdCheck(pl); break;
                case 2: openTeamRankingMenu(pl); break;
            }
        }
    });
}

/**
 * 获取团队在线队友数量（不包括自己）
 * 辅助函数，用于动态显示在线队友数量
 */
function getOnlineTeammatesCount(player, teamId) {
    const onlinePlayers = mc.getOnlinePlayers();
    let count = 0;
    
    for (let p of onlinePlayers) {
        if (p.xuid === player.xuid) continue;
        
        const pTeamId = getPlayerTeam(p);
        if (pTeamId === teamId) {
            count++;
        }
    }
    
    return count;
}

/**
 * 打开留言板主菜单
 * 添加冷却时间提示，并在打开时设置最后查看时间
 */
function openMessageBoard(player, teamId) {
    setLastMessageViewTime(player, teamId);
    
    const team = teamData[teamId];
    const messages = getTeamMessages(teamId);
    
    const cooldownCheck = checkMessageCooldown(teamId, player.xuid);
    let cooldownInfo = "";
    if (!cooldownCheck.canSend) {
        const minutes = Math.floor(cooldownCheck.remainingTime / 60);
        const seconds = cooldownCheck.remainingTime % 60;
        cooldownInfo = `\n§c§l留言冷却中：§r§f${minutes}分${seconds}秒后可以再次留言\n`;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【留言板】");
    
    let content = "§e团队：§f" + team.name + "\n§e活跃度：§f" + (team.activity || 0) + cooldownInfo + "\n";
    
    if (messages.length === 0) {
        content += "§7还没有留言，快来发布第一条留言吧！\n\n";
    } else {
        const recentMessages = messages.slice(0, 10);
        content += "§e最近留言：§7（共" + messages.length + "条）\n\n";
        
        for (let i = 0; i < recentMessages.length; i++) {
            const msg = recentMessages[i];
            const timeStr = formatMessageTime(msg.time);
            
            content += "§f" + (i + 1) + ". §e" + msg.senderName + " §7(" + timeStr + ")\n";
            content += "   §f" + msg.content + "\n\n";
        }
        
        if (messages.length > 10) {
            content += "§7...还有" + (messages.length - 10) + "条更早的留言\n\n";
        }
    }
    
    content += "§7留言板只保存最近十条留言！";
    
    form.setContent(content);
    
    if (cooldownCheck.canSend) {
        form.addButton("§2§l添加留言", "textures/menu_1/addliuyan");
    } else {
        form.addButton("§8§l添加留言（冷却中）", "textures/menu_1/addliuyan");
    }
    form.addButton("§l返回主菜单", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null) {
            openMainMenu(pl);
            return;
        }
        
        if (id === 0) {
            if (cooldownCheck.canSend) {
                openAddMessageMenu(pl, teamId);
            } else {
                const minutes = Math.floor(cooldownCheck.remainingTime / 60);
                const seconds = cooldownCheck.remainingTime % 60;
                openAlertMenu(pl, `§c留言冷却中！\n\n§7请等待§f${minutes}分${seconds}秒§7后再添加留言。`, () => {
                    openMessageBoard(pl, teamId);
                });
            }
        } else if (id === 1) {
            openMainMenu(pl);
        }
    });
}

/**
 * 打开添加留言菜单
 */
function openAddMessageMenu(player, teamId) {
    const form = mc.newCustomForm();
    form.setTitle("§l【添加留言】");
    
    form.addLabel("§e发布留言到留言板\n\n§7• 留言内容将在团队中公开可见\n• 请文明发言，尊重他人\n• 每条留言最多200字\n• 添加留言后10分钟内不能再次添加\n");
    form.addInput("§7留言内容", "我想说的话...", "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openMessageBoard(pl, teamId);
            return;
        }
        
        const messageContent = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        if (!messageContent || messageContent === "") {
            openAlertMenu(pl, "§c留言内容不能为空！", () => {
                openAddMessageMenu(pl, teamId);
            });
            return;
        }
        
        if (messageContent.length > 200) {
            openAlertMenu(pl, "§c留言内容过长！\n§7当前：" + messageContent.length + "字\n§7限制：200字", () => {
                openAddMessageMenu(pl, teamId);
            });
            return;
        }
        
        const success = addTeamMessage(teamId, pl, messageContent);
        
        if (success) {
            pl.tell("§a[团队系统] §f留言发布成功！\n§7下次留言需要等待10分钟冷却时间。");
            log("[MGTeam] 玩家 " + pl.realName + " 在团队 " + teamId + " 发布了留言");
            
            setTimeout(() => {
                openMessageBoard(pl, teamId);
            }, 500);
        } else {
            setTimeout(() => {
                openMessageBoard(pl, teamId);
            }, 500);
        }
    });
}

/**
 * 处理退出团队请求（检查管理员身份）
 */
function handleQuitTeam(player, teamId) {
    const team = teamData[teamId];
    
    if (isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c您是团队管理员，若要退出团队，请先将自己设置为普通成员后再退出或直接解散团队！", () => {
            openMainMenu(player);
        });
        return;
    }
    
    openQuitConfirmMenu(player, teamId);
}

/**
 * 打开团队管理菜单（修改后：添加公告设置按钮、团队公开性设置按钮和修改团队名称按钮）
 */
function openTeamManageMenu(player, teamId) {
    const team = teamData[teamId];
    const apps = getTeamApplications(teamId);
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【团队管理】");
    
    let noticeStatus = "§7未设置";
    if (team.notice && team.notice.trim() !== "") {
        noticeStatus = "§a已设置（" + team.notice.length + "字符）";
    }
    
    let publicStatus = team.isPublic ? "§a公开（可在排行榜中被查找）" : "§c私密";
    let friendlyFireStatus = team.allowFriendlyFire ? "§2已开启" : "§c已关闭";
    
    const teamActivity = team.activity || 0;
    
    form.setContent("§7团队名称：§f" + team.name + "\n§7团队ID：§f" + teamId + "\n§7团队公告：" + noticeStatus + "\n§7团队公开性：" + publicStatus + "\n§7成员误伤：" + friendlyFireStatus + "\n§7团队活跃度：§f" + teamActivity);
    
    form.addButton("§l管理团队成员\n§r§t设置权限与移除成员", "textures/menu_1/guanliplayer");
    if (apps.length > 0) {
        form.addButton("§l管理加入申请\n§r§c" + apps.length + "§2条新的申请！", "textures/menu_1/xindeshenqing");
    } else {
        form.addButton("§l管理加入申请\n§r§t暂无申请", "textures/menu_1/guanlishenqing");
    }
    
    form.addButton("§l编辑团队公告\n§r§t将展示在团队主菜单与排行榜中", "textures/menu_1/guanligonggao");
    
    form.addButton("§l团队积金流水\n§r§t查看最近50条积金变动记录", "textures/menu_1/tmmoney");
    
    form.addButton("§l修改团队名称\n§r§t当前名称：" + team.name, "textures/menu_1/guanligonggao");
    
    if (team.isPublic) {
        form.addButton("§l设置团队公开性\n§r§2当前状态：公开（可在排行榜中被查找）", "textures/menu_1/unlock");
    } else {
        form.addButton("§l设置团队公开性\n§r§t当前状态：私密", "textures/menu_1/lock");
    }
    
    if (team.allowFriendlyFire) {
        form.addButton("§l成员误伤\n§r§2当前状态：开启", "textures/menu_1/unlock");
    } else {
        form.addButton("§l成员误伤\n§r§c当前状态：关闭", "textures/menu_1/lock");
    }
    
    form.addButton("§c§l解散团队", "textures/menu_1/jiesan");
    form.addButton("§l返回主菜单", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null) {
            openMainMenu(pl);
            return;
        }
        
        switch (id) {
            case 0:
                openManageMembers(pl, teamId);
                break;
            case 1:
                openManageApplications(pl, teamId);
                break;
            case 2:
                openNoticeEditMenu(pl, teamId);
                break;
            case 3:
                openFundLogMenu(pl, teamId);
                break;
            case 4:
                openRenameTeamMenu(pl, teamId);
                break;
            case 5:
                toggleTeamPublicStatus(pl, teamId);
                break;
            case 6:
                toggleFriendlyFireStatus(pl, teamId);
                break;
            case 7:
                openDisbandConfirmMenu(pl, teamId);
                break;
            case 8:
                openMainMenu(pl);
                break;
        }
    });
}

/**
 * 打开修改团队名称菜单（新增函数）
 */
function openRenameTeamMenu(player, teamId) {
    const team = teamData[teamId];
    
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c只有团队管理员可以修改团队名称！", () => {
            openTeamManageMenu(player, teamId);
        });
        return;
    }
    
    const form = mc.newCustomForm();
    form.setTitle("§l【修改团队名称】");
    
    let labelText = "§e修改团队名称：\n\n";
    labelText += "§7• 名称长度必须在2-10个字符之间。\n";
    labelText += "§7• 不能与其他团队重名。\n\n";
    labelText += "§e§l当前团队名称：§f" + team.name;
    
    form.addLabel(labelText);
    form.addInput("§7新团队名称", "输入新的团队名称...", team.name);
    
    player.sendForm(form, (pl, data, reason) => {
        if (!isTeamOperator(pl, teamId)) {
            openAlertMenu(pl, "§c你当前不是团队管理员！", () => {
                openTeamManageMenu(pl, teamId);
            });
            return;
        }
        
        if (!data) {
            openTeamManageMenu(pl, teamId);
            return;
        }
        
        const newName = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        if (!newName || newName.length < 2 || newName.length > 10) {
            openAlertMenu(pl, "§c团队名称必须为2-10个字符！", () => {
                openRenameTeamMenu(pl, teamId);
            });
            return;
        }
        
        if (newName === team.name) {
            openAlertMenu(pl, "§c新名称与当前名称相同，无需修改！", () => {
                openRenameTeamMenu(pl, teamId);
            });
            return;
        }
        
        for (let id in teamData) {
            if (id !== teamId && teamData[id].name === newName) {
                openAlertMenu(pl, "§c已存在同名团队，请更换名称！", () => {
                    openRenameTeamMenu(pl, teamId);
                });
                return;
            }
        }
        
        openRenameConfirmMenu(pl, teamId, team.name, newName);
    });
}

/**
 * 打开修改团队名称确认菜单（新增函数）
 */
function openRenameConfirmMenu(player, teamId, oldName, newName) {
    const team = teamData[teamId];
    
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c你当前不是团队管理员！", () => {
            openTeamManageMenu(player, teamId);
        });
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【修改团队名称确认】");
    
    let content = "§e请确认修改：\n\n";
    content += "§e§l原团队名称：§f" + oldName + "\n";
    content += "§e§l新团队名称：§f" + newName + "\n\n";
    content += "§c确认修改团队名称？";
    
    form.setContent(content);
    form.addButton("§l返回修改", "textures/menu_1/lastpage");
    form.addButton("§2§l确认修改", "textures/menu_1/guanligonggao");
    
    player.sendForm(form, (pl, id, reason) => {
        if (!isTeamOperator(pl, teamId)) {
            openAlertMenu(pl, "§c你当前不是团队管理员！", () => {
                openTeamManageMenu(pl, teamId);
            });
            return;
        }
        
        if (id === null) {
            openRenameTeamMenu(pl, teamId);
            return;
        }
        
        if (id === 0) {
            openRenameTeamMenu(pl, teamId);
        } else if (id === 1) {
            executeRenameTeam(pl, teamId, oldName, newName);
        }
    });
}

/**
 * 执行修改团队名称（新增函数）
 */
function executeRenameTeam(player, teamId, oldName, newName) {
    const team = teamData[teamId];
    
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c你当前不是团队管理员！", () => {
            openMainMenu(player);
        });
        return;
    }
    
    for (let id in teamData) {
        if (id !== teamId && teamData[id].name === newName) {
            openAlertMenu(player, "§c修改失败，已存在同名团队！", () => {
                openTeamManageMenu(player, teamId);
            });
            return;
        }
    }
    
    const previousName = team.name;
    
    team.name = newName;
    
    saveData();
    
    player.tell("§a[团队系统] §f团队名称已从 §e" + oldName + " §f修改为 §e" + newName + "§f！");
    log("[MGTeam] 管理员 " + player.realName + " 将团队 " + teamId + " 的名称从 " + previousName + " 修改为 " + newName);
    
    const onlinePlayers = mc.getOnlinePlayers();
    for (let p of onlinePlayers) {
        const pTeamId = getPlayerTeam(p);
        if (pTeamId === teamId && p.xuid !== player.xuid) {
            p.tell("§e[团队系统] §f团队名称已由管理员修改：§e" + oldName + " §f→ §e" + newName);
        }
    }
    
    openTeamManageMenu(player, teamId);
}

/**
 * 切换团队公开状态
 */
function toggleTeamPublicStatus(player, teamId) {
    const team = teamData[teamId];
    
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c只有团队管理员可以设置团队公开性！", () => {
            openTeamManageMenu(player, teamId);
        });
        return;
    }
    
    team.isPublic = !team.isPublic;
    saveData();
    
    if (team.isPublic) {
        player.tell("§a[团队系统] §f团队已设为§a公开§f状态，其他玩家可以在排行榜中查找并申请加入！");
        log("[MGTeam] 管理员 " + player.realName + " 将团队 " + teamId + " 设为公开状态");
    } else {
        player.tell("§a[团队系统] §f团队已设为§c私密§f状态，其他玩家无法在排行榜中查找！");
        log("[MGTeam] 管理员 " + player.realName + " 将团队 " + teamId + " 设为私密状态");
    }
    
    openTeamManageMenu(player, teamId);
}

/**
 * 切换团队成员误伤状态
 */
function toggleFriendlyFireStatus(player, teamId) {
    const team = teamData[teamId];
    
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c只有团队管理员可以设置成员误伤！", () => {
            openTeamManageMenu(player, teamId);
        });
        return;
    }
    
    team.allowFriendlyFire = !team.allowFriendlyFire;
    saveData();
    
    if (team.allowFriendlyFire) {
        player.tell("§a[团队系统] §f成员误伤已§a开启");
        log("[MGTeam] 管理员 " + player.realName + " 将团队 " + teamId + " 的成员误伤设为开启状态");
    } else {
        player.tell("§a[团队系统] §f成员误伤已§c关闭");
        log("[MGTeam] 管理员 " + player.realName + " 将团队 " + teamId + " 的成员误伤设为关闭状态");
    }
    
    openTeamManageMenu(player, teamId);
}

/**
 * 打开团队详情页面（修改后：使用 moneyname 变量）
 */
function openTeamDetail(player, teamId) {
    const team = teamData[teamId];
    const form = mc.newSimpleForm();
    const isOperator = isTeamOperator(player, teamId);
    
    form.setTitle("§l【团队详情信息】");
    
    let content = "§e§l我的团队：§f" + team.name + "\n";
    content += "§7团队ID：§f" + teamId + "\n";
    
    if (isOperator) {
        content += "§6§l我的身份：§c§l团队管理员\n";
    } else {
        content += "§6§l我的身份：§a成员\n";
    }
    
    const teamActivity = team.activity || 0;
    content += "\n§e§l团队活跃度：§f" + teamActivity + "\n";
    
    if (team.notice && team.notice.trim() !== "") {
        const formattedNotice = team.notice.replace(/\\n/g, "\n").replace(/\n/g, "\n§f");
        content += "\n§e§l团队公告：§r\n" + formattedNotice;
    }
    
    content += "\n§e§l团队管理员：\n";
    if (team.operators && Array.isArray(team.operators)) {
        for (let op of team.operators) {
            content += "§f• " + getPlayerDisplayName(op) + "\n";
        }
    }
    content += "\n";
    
    content += "§e§l普通成员：\n";
    if (team.members && Array.isArray(team.members)) {
        if (team.members.length > 0) {
            for (let member of team.members) {
                content += "§f• " + getPlayerDisplayName(member) + "\n";
            }
        } else {
            content += "§7暂无普通成员\n";
        }
    } else {
        content += "§7暂无普通成员\n";
    }
    content += "\n";
    
    let memberCount = 0;
    if (team.members && Array.isArray(team.members)) {
        memberCount = team.members.length;
    }
    let operatorCount = team.operators ? team.operators.length : 0;
    content += "§e§l成员统计：§f" + (memberCount + operatorCount) + "人§7（管理员:" + operatorCount + "人，普通成员:" + memberCount + "人）\n\n";
    
    const teamFunds = team.funds || 0;
    // 修改：使用 moneyname 变量
    content += "§e§l团队资金：§f" + teamFunds + " §7" + moneyname + "\n\n";
    
    const apps = getTeamApplications(teamId);
    if (isOperator && apps.length > 0) {
        content += "§e§l待处理申请：§c" + apps.length + "条\n\n";
    }
    
    content += "-§7MGteam团队系统-";
    
    form.setContent(content);
    form.addButton("§l返回主菜单", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        openMainMenu(pl);
    });
}
/**
 * 彻底删除玩家的积金消费数据
 * @param {String} xuid - 玩家XUID
 */
function clearFundConsumeData(xuid) {
    if (fundConsumeData[xuid]) {
        delete fundConsumeData[xuid];
        saveFundConsumeData();
        log("[MGTeam] 已清理玩家 " + xuid + " 的积金消费数据");
    }
}
/**
 * 初始化积金消费开关数据文件
 */
function initFundConsumeFile() {
    try {
        fundConsumeConfigFile = new JsonConfigFile("plugins/MGTeam/MGteamdata_fundconsume.json", "{}");

        const content = fundConsumeConfigFile.read();
        let fullData = content ? JSON.parse(content) : {};

        // 兼容性处理：如果包含 'status' 键，说明是新格式
        if (fullData && fullData.hasOwnProperty('status')) {
            fundConsumeData = fullData.status || {};
            fundLogs = fullData.logs || {};
        } else {
            // 旧格式：整个对象就是 fundConsumeData
            fundConsumeData = fullData || {};
            fundLogs = {};
        }

        log("[MGTeam] 已加载积金消费开关数据与流水记录");
    } catch (err) {
        log("[MGTeam] 积金消费开关数据文件初始化失败: " + err);
        fundConsumeData = {};
        fundLogs = {};
    }
}

/**
 * 保存积金消费开关数据到文件
 */
function saveFundConsumeData() {
    try {
        if (fundConsumeConfigFile) {
            let dataToSave = {
                status: fundConsumeData,
                logs: fundLogs
            };
            fundConsumeConfigFile.write(JSON.stringify(dataToSave, null, 4));
        }
    } catch (err) {
        log("[MGTeam] 保存积金消费开关数据失败: " + err);
    }
}

/**
 * 获取玩家的积金消费开关状态
 * @param {String} xuid - 玩家XUID
 * @returns {Boolean} 开关状态，默认为false（关闭）
 */
function getFundConsumeStatus(xuid) {
    if (!fundConsumeData[xuid]) {
        return false;
    }
    return fundConsumeData[xuid].enabled === true;
}

/**
 * 设置玩家的积金消费开关状态
 * @param {String} xuid - 玩家XUID
 * @param {Boolean} enabled - 开关状态
 */
function setFundConsumeStatus(xuid, enabled) {
    fundConsumeData[xuid] = {
        enabled: enabled,
        updatedAt: new Date().toISOString()
    };
    saveFundConsumeData();
}

/**
 * 切换玩家的积金消费开关状态（修改后：使用 moneyname 变量）
 */
function toggleFundConsumeStatus(player) {
    const xuid = player.xuid;
    const currentStatus = getFundConsumeStatus(xuid);
    const newStatus = !currentStatus;

    setFundConsumeStatus(xuid, newStatus);

    if (newStatus) {
        // 修改：使用 moneyname 变量
        player.tell("§a[团队积金] §f§a已开启§f积金消费保护！\n§7当你产生消费时，团队积金将为你垫付。");
        log("[MGTeam] 玩家 " + player.realName + " 开启了积金消费保护");
    } else {
        player.tell("§a[团队积金] §f§c已关闭§f积金消费保护！");
        log("[MGTeam] 玩家 " + player.realName + " 关闭了积金消费保护");
    }

    return newStatus;
}

/**
 * 初始化玩家余额监控
 */
function initMoneyMonitor() {
    moneyMonitorTimer = setInterval(() => {
        checkPlayersMoneyChange();
    }, 5000);

    log("[MGTeam] 玩家余额监控已启动，每5秒检查一次");
}

/**
 * 检查所有在线玩家的余额变化
 */
function checkPlayersMoneyChange() {
    try {
        const onlinePlayers = mc.getOnlinePlayers();

        for (let player of onlinePlayers) {
            const xuid = player.xuid;
            const currentMoney = player.getMoney();

            if (getFundConsumeStatus(xuid)) {
                if (playerMoneyMonitor.hasOwnProperty(xuid)) {
                    const lastMoney = playerMoneyMonitor[xuid];

                    if (currentMoney < lastMoney) {
                        const diff = lastMoney - currentMoney;
                        handleMoneyDecrease(player, diff);
                    }
                }
            }

            playerMoneyMonitor[xuid] = currentMoney;
        }
    } catch (err) {
        log("[MGTeam] 检查余额变化时出错: " + err);
    }
}

/**
 * 处理玩家余额减少（开启积金消费保护时）
 * @param {Player} player - 玩家对象
 * @param {Number} amount - 减少的金额
 */
/**
 * 处理玩家余额减少（开启积金消费保护时）（修改后：使用 moneyname 变量）
 */
function handleMoneyDecrease(player, amount) {
    try {
        const teamId = getPlayerTeam(player);
        if (!teamId) return;

        const team = teamData[teamId];
        if (!team) return;

        const teamFunds = team.funds || 0;

        if (teamFunds > amount) {
            team.funds = teamFunds - amount;
            saveData();

            const addSuccess = player.addMoney(amount);

            if (addSuccess) {
                // 修改：使用 moneyname 变量
                player.tell("§a[团队积金] §f此次消费由你的团队积金垫付！积金剩余：§e" + team.funds + " §7" + moneyname);
                log("[MGTeam] 玩家 " + player.realName + " 消费 " + amount + " "+ moneyname +"，已从团队 " + teamId + " 积金中补偿");
            } else {
                team.funds = teamFunds;
                saveData();
                log("[MGTeam] 为玩家 " + player.realName + " 补偿积金失败，已回滚团队积金");
            }
        } else {
            // 修改：使用 moneyname 变量
            player.tell("§c[团队积金] §f团队积金不足，无法垫付。");
        }
    } catch (err) {
        log("[MGTeam] 处理余额减少时出错: " + err);
    }
}

/**
 * 打开团队资金菜单（修改后：使用 moneyname 变量）
 */
function openTeamFundMenu(player, teamId) {
    const team = teamData[teamId];
    const teamFunds = team.funds || 0;
    const teamActivity = team.activity || 0;

    const fundConsumeEnabled = getFundConsumeStatus(player.xuid);
    const fundConsumeStatusText = fundConsumeEnabled ? " §2开" : " §c关";
    const fundConsumeButtonIcon = fundConsumeEnabled ? "textures/menu_1/xiaofei" : "textures/menu_1/xiaofei";

    const form = mc.newSimpleForm();
    form.setTitle("§l【团队积金】");
    // 修改：使用 moneyname 变量
    form.setContent("§e团队积金管理\n\n§e§l我的团队：§f" + team.name + "\n§e§l团队积金：§f" + teamFunds + " §7" + moneyname + "\n\n§r§7选择操作：");

    form.addButton("§2§l存入积金", "textures/menu_1/addtmmoney");
    form.addButton("§c§l取出积金", "textures/menu_1/gettmmoney");
    form.addButton("§l积金消费：" + fundConsumeStatusText + "\n§r§t由团队积金自动垫付你的消费", fundConsumeButtonIcon);
    form.addButton("§l返回主菜单", "textures/menu_1/lastpage");

    player.sendForm(form, (pl, id, reason) => {
        if (id === null) {
            openMainMenu(pl);
            return;
        }

        switch (id) {
            case 0:
                openDepositMenu(pl, teamId);
                break;
            case 1:
                openWithdrawMenu(pl, teamId);
                break;
            case 2:
                toggleFundConsumeStatus(pl);
                setTimeout(() => {
                    openTeamFundMenu(pl, teamId);
                }, 500);
                break;
            case 3:
                openMainMenu(pl);
                break;
        }
    });
}

/**
 * 打开存入资金菜单（修改后：使用 moneyname 变量）
 */
function openDepositMenu(player, teamId) {
    const team = teamData[teamId];
    const playerMoney = player.getMoney();
    const teamFunds = team.funds || 0;
    
    const form = mc.newCustomForm();
    form.setTitle("§l【存入资金】");
    // 修改：使用 moneyname 变量
    form.addLabel("§e存入资金到团队账户\n\n§e§l我的余额：§f" + playerMoney + " §7" + moneyname + "\n§e§l团队资金：§f" + teamFunds + " §7" + moneyname);
    form.addInput("§7请输入存入金额（正整数）", "例如：100", "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openTeamFundMenu(pl, teamId);
            return;
        }
        
        const amountStr = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        const validation = validateAmount(amountStr);
        if (!validation.valid) {
            openAlertMenu(pl, validation.message, () => {
                openDepositMenu(pl, teamId);
            });
            return;
        }
        
        const amount = validation.value;
        
        const currentMoney = pl.getMoney();
        if (currentMoney < amount) {
            // 修改：使用 moneyname 变量
            openAlertMenu(pl, "§c你的余额不足！\n\n§7我的余额：§f" + currentMoney + " §7" + moneyname + "\n§7存入金额：§f" + amount + " §7" + moneyname, () => {
                openDepositMenu(pl, teamId);
            });
            return;
        }
        
        executeDeposit(pl, teamId, amount);
    });
}

/**
 * 执行存款操作（修改后：使用 moneyname 变量）
 */
function executeDeposit(player, teamId, amount) {
    const team = teamData[teamId];
    
    const success = player.reduceMoney(amount);
    if (!success) {
        openAlertMenu(player, "§c扣除个人资金失败，请重试！", () => {
            openDepositMenu(player, teamId);
        });
        return;
    }
    
    team.funds = (team.funds || 0) + amount;
    
    // 记录流水账
    addFundLog(teamId, amount, `玩家 ${player.realName} 存入`);
    
    saveData();
    
    const currentMoney = player.getMoney();
    // 修改：使用 moneyname 变量
    player.tell("§a[团队系统] §f成功存入 §e" + amount + " §f" + moneyname + "到团队资金！");
    player.tell("§a[团队系统] §f我的余额：§e" + currentMoney + " §f" + moneyname + "，团队资金：§e" + team.funds + " §f" + moneyname);
    log("[MGTeam] 玩家 " + player.realName + " 存入 " + amount + " "+ moneyname +"到团队 " + teamId);
    
    openTeamFundMenu(player, teamId);
}

/**
 * 打开取出资金菜单（修改后：使用 moneyname 变量）
 */
function openWithdrawMenu(player, teamId) {
    const team = teamData[teamId];
    const teamFunds = team.funds || 0;
    
    const form = mc.newCustomForm();
    form.setTitle("§l【取出资金】");
    // 修改：使用 moneyname 变量
    form.addLabel("§e从团队账户取出资金\n\n§e§l团队资金：§f" + teamFunds + " §7" + moneyname + "\n");
    form.addInput("§7请输入取出金额（正整数）", "例如：100", "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openTeamFundMenu(pl, teamId);
            return;
        }
        
        const amountStr = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        const validation = validateAmount(amountStr);
        if (!validation.valid) {
            openAlertMenu(pl, validation.message, () => {
                openWithdrawMenu(pl, teamId);
            });
            return;
        }
        
        const amount = validation.value;
        
        if (teamFunds < amount) {
            // 修改：使用 moneyname 变量
            openAlertMenu(pl, "§c团队资金不足！\n\n§7团队资金：§f" + teamFunds + " §7" + moneyname + "\n§7取出金额：§f" + amount + " §7" + moneyname, () => {
                openWithdrawMenu(pl, teamId);
            });
            return;
        }
        
        executeWithdraw(pl, teamId, amount);
    });
}

/**
 * 执行取款操作（修改后：使用 moneyname 变量）
 */
function executeWithdraw(player, teamId, amount) {
    const team = teamData[teamId];
    
    team.funds = (team.funds || 0) - amount;
    
    // 记录流水账
    addFundLog(teamId, -amount, `玩家 ${player.realName} 取出`);
    
    const success = player.addMoney(amount);
    if (!success) {
        team.funds = team.funds + amount;
        openAlertMenu(player, "§c增加个人资金失败，已回滚团队资金，请重试！", () => {
            openWithdrawMenu(player, teamId);
        });
        return;
    }
    
    saveData();
    
    const currentMoney = player.getMoney();
    // 修改：使用 moneyname 变量
    player.tell("§a[团队系统] §f成功从团队资金取出 §e" + amount + " §f" + moneyname + "！");
    player.tell("§a[团队系统] §f我的余额：§e" + currentMoney + " §f" + moneyname + "，团队资金：§e" + team.funds + " §f" + moneyname);
    log("[MGTeam] 玩家 " + player.realName + " 从团队 " + teamId + " 取出 " + amount + " "+ moneyname +"");
    
    openTeamFundMenu(player, teamId);
}
/**
 * 验证金额输入（新增函数）
 * 规则：必须是正整数，不能是小数、负数或零
 */
function validateAmount(input) {
    if (!input || input === "") {
        return {
            valid: false,
            message: "§c请输入金额！"
        };
    }
    
    if (input.indexOf(".") !== -1 || input.indexOf(",") !== -1) {
        return {
            valid: false,
            message: "§c金额不能包含小数！\n§7请输入正整数（如：100）"
        };
    }
    
    const trimmed = input.trim();
    if (!/^\d+$/.test(trimmed)) {
        if (trimmed.indexOf("-") !== -1) {
            return {
                valid: false,
                message: "§c金额不能为负数！\n§7请输入正整数"
            };
        }
        return {
            valid: false,
            message: "§c请输入有效的正整数金额！\n§7只能包含数字，不能包含字母或特殊字符"
        };
    }
    
    const amount = parseInt(trimmed, 10);
    
    if (isNaN(amount) || amount <= 0) {
        return {
            valid: false,
            message: "§c金额必须是大于0的正整数！"
        };
    }
    
    if (amount > 9007199254740991) {
        return {
            valid: false,
            message: "§c金额过大！\n§7请输入更小的数值"
        };
    }
    
    return {
        valid: true,
        value: amount
    };
}

/**
 * 打开管理团队成员页面（修改后：添加身份相同检测）
 */
function openManageMembers(player, teamId) {
    const team = teamData[teamId];

    // 加强修复：每次打开时检测玩家是否仍为管理员
    if (!isTeamOperator(player, teamId)) {
        // 已不是管理员，返回团队详情菜单
        openAlertMenu(player, "§c你当前不是团队管理员，无法管理成员！", () => {
            openTeamDetail(player, teamId);
        });
        return;
    }

    // 构建成员列表（管理员+普通成员）
    const memberList = [];

    // 添加管理员
    if (team.operators && Array.isArray(team.operators)) {
        for (let op of team.operators) {
            memberList.push({
                xuid: op.xuid,
                name: op.name,
                type: "operator",
                displayName: "管理员-" + getPlayerPlainDisplayName(op)
            });
        }
    }

    // 添加普通成员
    if (team.members && Array.isArray(team.members)) {
        for (let member of team.members) {
            memberList.push({
                xuid: member.xuid,
                name: member.name,
                type: "member",
                displayName: "普通成员-" + getPlayerPlainDisplayName(member)
            });
        }
    }

    if (memberList.length === 0) {
        openAlertMenu(player, "§c团队成员列表为空！", () => {
            openTeamDetail(player, teamId);
        });
        return;
    }

    // 创建 CustomForm 对象
    const form = mc.newCustomForm();

    form.setTitle("§6§l【MGteam·团队系统】");
    form.addLabel("§e请在名单中选择成员：");

    // 准备下拉菜单选项
    const displayNames = [];
    for (let m of memberList) {
        displayNames.push(m.displayName);
    }

    form.addDropdown("§7选择成员", displayNames);
    form.addLabel("§e请选择操作：");
    form.addDropdown("§7操作类型", ["设置为管理员", "设置为普通成员", "移出团队"]);

    player.sendForm(form, (pl, data, reason) => {
        // 加强修复：回调中再次检测是否仍为管理员
        if (!isTeamOperator(pl, teamId)) {
            openAlertMenu(pl, "§c你当前不是团队管理员，无法管理成员！", () => {
                openTeamDetail(pl, teamId);
            });
            return;
        }

        if (!data) {
            openTeamDetail(pl, teamId);
            return;
        }

        // 使用正确的索引
        const selectedIndex = parseInt(data[1]);
        const operationType = parseInt(data[3]);

        // // 调试日志
        // //log("[MGTeam Debug] data数组: " + JSON.stringify(data));
        // //log("[MGTeam Debug] 成员索引: " + selectedIndex + ", 操作类型: " + operationType);

        // 检查是否为有效数字
        if (isNaN(selectedIndex) || isNaN(operationType)) {
            log("[MGTeam Error] 无效的数据 - selectedIndex: " + selectedIndex + ", operationType: " + operationType);
            openAlertMenu(pl, "§c表单数据异常，请重试！", () => {
                openManageMembers(pl, teamId);
            });
            return;
        }

        // 有效性检查
        if (selectedIndex < 0 || selectedIndex >= memberList.length) {
            openAlertMenu(pl, "§c选择的成员无效！", () => {
                openManageMembers(pl, teamId);
            });
            return;
        }

        const selectedMember = memberList[selectedIndex];

        // 修改：检测身份相同的情况
        // operationType: 0=设置为管理员, 1=设置为普通成员, 2=移出团队
        
        // 如果目标是管理员，且操作是"设置为管理员"
        if (selectedMember.type === "operator" && operationType === 0) {
            openAlertMenu(pl, "§c该玩家已经是管理员！\n§7无需重复设置。", () => {
                openManageMembers(pl, teamId);
            });
            return;
        }
        
        // 如果目标是普通成员，且操作是"设置为普通成员"
        if (selectedMember.type === "member" && operationType === 1) {
            openAlertMenu(pl, "§c该玩家已经是普通成员！\n§7无需重复设置。", () => {
                openManageMembers(pl, teamId);
            });
            return;
        }

        // 如果是自己且操作是移出团队，特殊处理
        if (selectedMember.xuid === pl.xuid && operationType === 2) {
            openAlertMenu(pl, "§c您是团队管理员，若要退出团队，请先将自己设置为普通成员后再退出或直接解散团队！", () => {
                openManageMembers(pl, teamId);
            });
            return;
        }

        // 检查管理员数量不足的情况（包括自己降为成员）
        if (selectedMember.type === "operator") {
            const operatorCount = team.operators ? team.operators.length : 0;
            // 管理员数量必须大于1才能进行降级/移出操作（确保至少留一个管理员）
            if (operatorCount <= 1 && (operationType === 1 || operationType === 2)) {
                openAlertMenu(pl, "§c当前团队管理员数量不足，无法进行操作！", () => {
                    openManageMembers(pl, teamId);
                });
                return;
            }
        }

        // 打开二次确认
        openMemberOperationConfirm(pl, teamId, selectedMember, operationType);
    });
}

/**
 * 打开成员操作确认页面
 */
function openMemberOperationConfirm(player, teamId, member, operationType) {
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c你当前不是团队管理员，无法管理成员！", () => {
            openTeamDetail(player, teamId);
        });
        return;
    }
    
    const opType = Number(operationType);
    ////log("[MGTeam Debug] operationType原始值: " + operationType + ", 类型: " + typeof operationType + ", 转换后: " + opType);
    
    let operationName = "未知操作";
    let confirmColor = "§f";
    
    if (opType === 0) {
        operationName = "设置为管理员";
        confirmColor = "§a";
    } else if (opType === 1) {
        operationName = "设置为普通成员";
        confirmColor = "§e";
    } else if (opType === 2) {
        operationName = "移出团队";
        confirmColor = "§c";
    } else {
        log("[MGTeam Error] 无效的操作类型: " + operationType);
        openAlertMenu(player, "§c无效的操作类型: " + operationType, () => {
            openManageMembers(player, teamId);
        });
        return;
    }
    
    //log("[MGTeam Debug] 最终操作名称: " + operationName + ", 颜色: " + confirmColor);
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【团队系统】");
    
    const content = "§e请确认操作：\n\n" +
        "§7目标成员：" + getPlayerDisplayName(member) + "\n" +
        "§7当前身份：§f" + (member.type === "operator" ? "管理员" : "普通成员") + "\n" +
        "§7执行操作：§f" + operationName + "\n\n" +
        "§c- 注意：管理员拥有团队内所有权限！包含移除成员、移除传送点，甚至是解散团队！\n";
    
    form.setContent(content);
    
    const confirmButtonText = confirmColor + "§l确认" + operationName;
    //log("[MGTeam Debug] 确认按钮文本: " + confirmButtonText);
    
    form.addButton("§l取消", "textures/ui/cancel");
    form.addButton(confirmButtonText, "textures/menu_1/right");
    
    player.sendForm(form, (pl, id, reason) => {
        if (!isTeamOperator(pl, teamId)) {
            openAlertMenu(pl, "§c你当前不是团队管理员，无法管理成员！", () => {
                openTeamDetail(pl, teamId);
            });
            return;
        }
        
        //log("[MGTeam Debug] 表单回调 - id: " + id + ", reason: " + reason);
        
        if (id === null) {
            //log("[MGTeam Debug] 玩家关闭表单");
            openManageMembers(pl, teamId);
            return;
        }
        
        if (id === 0) {
            //log("[MGTeam Debug] 玩家点击取消");
            openManageMembers(pl, teamId);
            return;
        }
        
        if (id === 1) {
            //log("[MGTeam Debug] 玩家点击确认，执行操作: " + opType);
            executeMemberOperation(pl, teamId, member, opType);
        }
    });
}

/**
 * 执行成员操作（实际数据修改）
 */
function executeMemberOperation(player, teamId, member, operationType) {
    const team = teamData[teamId];
    
    const opType = Number(operationType);
    //log("[MGTeam Debug] 执行操作 - 类型: " + opType + ", 成员: " + member.name);
    
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c你当前不是团队管理员，无法管理成员！", () => {
            openTeamDetail(player, teamId);
        });
        return;
    }
    
    if (member.xuid === player.xuid && opType === 0) {
        openAlertMenu(player, "§c您已经是管理员了，无需重复设置！", () => {
            openManageMembers(player, teamId);
        });
        return;
    }
    
    if (member.xuid === player.xuid && opType === 2) {
        openAlertMenu(player, "§c您是团队管理员，若要退出团队，请先将自己设置为普通成员后再退出或直接解散团队！", () => {
            openManageMembers(player, teamId);
        });
        return;
    }
    
    if (member.type === "operator") {
        const operatorCount = team.operators ? team.operators.length : 0;
        if (operatorCount <= 1 && (opType === 1 || opType === 2)) {
            openAlertMenu(player, "§c当前团队管理员数量不足，无法进行操作！", () => {
                openManageMembers(player, teamId);
            });
            return;
        }
    }
    
    let isSelfDemote = false;
    
    if (opType === 0) {
        if (team.members && Array.isArray(team.members)) {
            team.members = team.members.filter(m => m.xuid !== member.xuid);
        }
        if (!team.operators) team.operators = [];
        team.operators.push({
            xuid: member.xuid,
            name: member.name
        });
        player.tell("§a[团队系统] §f已将 §e" + member.name + " §f设置为管理员！");
        log("[MGTeam] 管理员 " + player.realName + " 将 " + member.name + " 设为管理员");
        
    } else if (opType === 1) {
        if (member.xuid === player.xuid) isSelfDemote = true;
        
        if (team.operators && Array.isArray(team.operators)) {
            team.operators = team.operators.filter(m => m.xuid !== member.xuid);
        }
        if (!team.members) team.members = [];
        team.members.push({
            xuid: member.xuid,
            name: member.name
        });
        player.tell("§a[团队系统] §f已将 §e" + member.name + " §f设置为普通成员！");
        log("[MGTeam] 管理员 " + player.realName + " 将 " + member.name + " 设为普通成员");
        
    } else if (opType === 2) {
        if (member.type === "operator") {
            if (team.operators && Array.isArray(team.operators)) {
                team.operators = team.operators.filter(m => m.xuid !== member.xuid);
            }
        } else {
            if (team.members && Array.isArray(team.members)) {
                team.members = team.members.filter(m => m.xuid !== member.xuid);
            }
        }
        player.tell("§a[团队系统] §f已将 §e" + member.name + " §f移出团队！");
        log("[MGTeam] 管理员 " + player.realName + " 将 " + member.name + " 移出团队");
        
        const onlinePlayers = mc.getOnlinePlayers();
        for (let p of onlinePlayers) {
            if (p.xuid === member.xuid) {
                p.tell("§c[团队系统] §f你已被移出团队 §e" + team.name + "§f！");
                break;
            }
        }
        
    } else {
        log("[MGTeam Error] 执行时遇到无效操作类型: " + opType);
        openAlertMenu(player, "§c无效的操作类型！", () => {
            openManageMembers(player, teamId);
        });
        return;
    }
    
    saveData();
    
    if (isSelfDemote) {
        openTeamDetail(player, teamId);
    } else {
        openManageMembers(player, teamId);
    }
}

/**
 * 执行成员操作
 */
function executeMemberOperation(player, teamId, member, operationType) {
    const team = teamData[teamId];
    
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c你当前不是团队管理员，无法管理成员！", () => {
            openTeamDetail(player, teamId);
        });
        return;
    }
    
    if (member.xuid === player.xuid && operationType === 0) {
        openAlertMenu(player, "§c您已经是管理员了，无需重复设置！", () => {
            openManageMembers(player, teamId);
        });
        return;
    }
    
    if (member.xuid === player.xuid && operationType === 2) {
        openAlertMenu(player, "§c您是团队管理员，若要退出团队，请先将自己设置为普通成员后再退出或直接解散团队！", () => {
            openManageMembers(player, teamId);
        });
        return;
    }
    
    if (member.type === "operator") {
        const operatorCount = team.operators ? team.operators.length : 0;
        if (operatorCount <= 1 && (operationType === 1 || operationType === 2)) {
            openAlertMenu(player, "§c当前团队管理员数量不足，无法进行操作！", () => {
                openManageMembers(player, teamId);
            });
            return;
        }
    }
    
    let isSelfDemote = false;
    
    switch (operationType) {
        case 0:
            if (team.members && Array.isArray(team.members)) {
                team.members = team.members.filter(m => m.xuid !== member.xuid);
            }
            if (!team.operators) {
                team.operators = [];
            }
            team.operators.push({
                xuid: member.xuid,
                name: member.name
            });
            player.tell("§a[团队系统] §f已将 §e" + member.name + " §f设置为管理员！");
            log("[MGTeam] 管理员 " + player.realName + " 将 " + member.name + " 设为管理员");
            break;
            
        case 1:
            if (member.xuid === player.xuid) {
                isSelfDemote = true;
            }
            
            if (team.operators && Array.isArray(team.operators)) {
                team.operators = team.operators.filter(m => m.xuid !== member.xuid);
            }
            if (!team.members) {
                team.members = [];
            }
            team.members.push({
                xuid: member.xuid,
                name: member.name
            });
            player.tell("§a[团队系统] §f已将 §e" + member.name + " §f设置为普通成员！");
            log("[MGTeam] 管理员 " + player.realName + " 将 " + member.name + " 设为普通成员");
            break;
            
            case 2:
                if (member.type === "operator") {
                    if (team.operators && Array.isArray(team.operators)) {
                        team.operators = team.operators.filter(m => m.xuid !== member.xuid);
                    }
                } else {
                    if (team.members && Array.isArray(team.members)) {
                        team.members = team.members.filter(m => m.xuid !== member.xuid);
                    }
                }
                player.tell("§a[团队系统] §f已将 §e" + member.name + " §f移出团队！");
                log("[MGTeam] 管理员 " + player.realName + " 将 " + member.name + " 移出团队");
                
                // 清理被移出玩家的积金消费数据
                clearFundConsumeData(member.xuid);
                
                const onlinePlayers = mc.getOnlinePlayers();
                for (let p of onlinePlayers) {
                    if (p.xuid === member.xuid) {
                        p.tell("§c[团队系统] §f你已被移出团队 §e" + team.name + "§f！");
                        break;
                    }
                }
                break;
    }
    
    saveData();
    
    if (isSelfDemote) {
        openTeamDetail(player, teamId);
    } else {
        openManageMembers(player, teamId);
    }
}

/**
 * 打开解散团队确认菜单
 */
function openDisbandConfirmMenu(player, teamId) {
    const team = teamData[teamId];
    const form = mc.newCustomForm();
    
    form.setTitle("§l【团队系统】");
    form.addLabel("§c§l你真的要解散团队吗？\n\n§c§l-此操作不可撤销！\n");
    form.addLabel("§7若要解散，请在下方输入团队名称：§f" + team.name);
    form.addInput("§7团队名称确认", "请输入：" + team.name, "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openTeamDetail(pl, teamId);
            return;
        }
        
        const inputName = (data[2] !== undefined && data[2] !== null) ? String(data[2]).trim() : "";
        
        if (inputName !== team.name) {
            openAlertMenu(pl, "§c团队名称输入错误，解散失败！", () => {
                openDisbandConfirmMenu(pl, teamId);
            });
            return;
        }
        
        disbandTeam(pl, teamId);
       openMainMenu(player);})} 
/**
 * 解散团队
 */
function disbandTeam(player, teamId) {
    const team = teamData[teamId];
    const teamName = team.name;
    
    // 清理所有团队成员的积金消费数据
    if (team.operators && Array.isArray(team.operators)) {
        for (let op of team.operators) {
            clearFundConsumeData(op.xuid);
        }
    }
    if (team.members && Array.isArray(team.members)) {
        for (let member of team.members) {
            clearFundConsumeData(member.xuid);
        }
    }
    
    delete teamData[teamId];
    
    if (messageData[teamId]) {
        delete messageData[teamId];
        saveMessageData();
    }
    
    saveData();
    
    player.tell("§a[团队系统] §f团队 §e" + teamName + " §f已成功解散！");
    log("[MGTeam] 管理员 " + player.realName + " 解散了团队 " + teamName + " (ID: " + teamId + ")");
    
    openMainMenu(player);
}
/**
 * 打开退出队伍确认菜单（保持不变）
 */
function openQuitConfirmMenu(player, teamId) {
    const team = teamData[teamId];
    const form = mc.newCustomForm();
    
    form.setTitle("§l【团队系统】");
    form.addLabel("§e你真的要退出队伍吗？\n\n§c§l团队名称：§f" + team.name + "\n");
    form.addLabel("§7若要退出，请在下方输入 §ayes §7确认：");
    form.addInput("§7确认退出", "请输入：yes", "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openMainMenu(pl);
            return;
        }
        
        const input = (data[2] !== undefined && data[2] !== null) ? String(data[2]).trim().toLowerCase() : "";
        
        if (input !== "yes") {
            openAlertMenu(pl, "§c确认信息输入错误，退出失败！", () => {
                openQuitConfirmMenu(pl, teamId);
            });
            return;
        }
        
        quitTeam(pl, teamId);
    });
}

/**
 * 退出队伍
 */
function quitTeam(player, teamId) {
    const team = teamData[teamId];
    const teamName = team.name;
    
    if (team.members && Array.isArray(team.members)) {
        team.members = team.members.filter(member => member.xuid !== player.xuid);
    }
    
    // 清理该玩家的积金消费数据
    clearFundConsumeData(player.xuid);
    
    saveData();
    
    player.tell("§a[团队系统] §f你已退出团队 §e" + teamName + "§f！");
    log("[MGTeam] 玩家 " + player.realName + " 退出了团队 " + teamName + " (ID: " + teamId + ")");
    
    openMainMenu(player);
}

/**
 * 通过ID加入团队前的时长检查（修改后：添加开关判断）
 */
function openJoinByIdCheck(player) {
    // 修改：添加 EnablePlaytimeCheck 开关判断
    if (EnablePlaytimeCheck) {
        const checkResult = checkPlaytimeRequirement(player);
        
        if (!checkResult.valid) {
            const form = mc.newSimpleForm();
            
            form.setTitle("§l【团队系统】");
            form.setContent("§c§l您的当前在线时长" + checkResult.current + "分钟不满足要求（600分钟），无法加入或创建团队！\n\n§e你当前的在线时长：§f" + checkResult.current + " 分钟\n§e使用团队功能需要的在线时长：§f" + checkResult.required + " 分钟\n\n§7请继续在线游戏积累时长后再试。");
            
            form.addButton("§l返回", "textures/menu_1/lastpage");
            
            player.sendForm(form, (pl, id, reason) => {
                if (id === null || id === 0) {
                    openMainMenu(pl);
                    return;
                }
            });
            return;
        }
    }
    
    openJoinByIdInput(player);
}

/**
 * 打开输入团队ID表单
 */
function openJoinByIdInput(player) {
    const form = mc.newCustomForm();
    
    form.setTitle("§l【团队系统】");
    form.addLabel("§e输入团队ID以申请加入团队：\n\n§7• 团队ID为4位字符\n§7• 向已有的团队成员获取正确ID");
    form.addInput("§7团队ID", "请输入4位团队ID", "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openMainMenu(pl);
            return;
        }
        
        const inputId = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        if (!inputId || inputId.length !== 4) {
            openAlertMenu(pl, "§c团队ID必须为4位字符！", () => {
                openJoinByIdInput(pl);
            });
            return;
        }
        
        const team = teamData[inputId];
        
        if (!team) {
            openAlertMenu(pl, "§c未找到团队ID为 §e" + inputId + " §c的团队！", () => {
                openJoinByIdInput(pl);
            });
            return;
        }
        
        openTeamApplyConfirm(pl, inputId, team);
    });
}

/**
 * 打开团队申请确认页面（修改2：新增团队公告与团队资金展示）
 */
/**
 * 打开团队申请确认页面（修改后：使用 moneyname 变量）
 */
function openTeamApplyConfirm(player, teamId, team) {
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【团队系统】");
    
    let content = "§e找到以下团队：\n\n";
    content += "§e§l团队名称：§f" + team.name + "\n";
    content += "§7团队ID：§f" + teamId + "\n";
    content += "§e§l管理员：§f" + (team.operators && team.operators.length > 0 ? team.operators[0].name : "未知") + "\n";
    
    if (team.notice && team.notice.trim() !== "") {
        const formattedNotice = team.notice.replace(/\\n/g, "\n").replace(/\n/g, "\n§f");
        content += "§e§l团队公告：§r\n" + formattedNotice + "\n";
    }
    
    const teamActivity = team.activity || 0;
    content += "§e§l团队活跃度：§f" + teamActivity + "\n";
    
    const teamFunds = team.funds || 0;
    // 修改：使用 moneyname 变量
    content += "§e§l团队资金：§f" + teamFunds + " §7" + moneyname + "\n";
    
    let memberCount = 0;
    if (team.members && Array.isArray(team.members)) {
        memberCount = team.members.length;
    }
    let operatorCount = team.operators ? team.operators.length : 0;
    content += "§e§l成员数量：§f" + (memberCount + operatorCount) + "人§7（含管理员）\n\n";
    content += "§7确认要向该团队发送入队申请吗？";
    
    form.setContent(content);
    form.addButton("§l返回", "textures/ui/cancel");
    form.addButton("§2§l确定", "textures/menu_1/right");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null) {
            openJoinByIdInput(pl);
            return;
        }
        
        if (id === 0) {
            openMainMenu(pl);
        } else if (id === 1) {
            sendTeamApply(pl, teamId, team);
        }
    });
}

/**
 * 发送团队申请（实装版）
 */
function sendTeamApply(player, teamId, team) {
    const existingTeamId = hasPendingApplication(player.xuid);
    
    if (existingTeamId) {
        openReplaceApplicationConfirm(player, teamId, team, existingTeamId);
        return;
    }
    
    submitApplication(player, teamId, team);
}

/**
 * 打开替换申请确认界面
 */
function openReplaceApplicationConfirm(player, teamId, team, oldTeamId) {
    const oldTeam = teamData[oldTeamId];
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【团队系统】");
    form.setContent("§e存在未处理申请！\n\n§7当前申请加入的团队：§f" + (oldTeam ? oldTeam.name : "未知团队") + "\n§7新申请加入的团队：§f" + team.name + "\n\n§c发送新申请的同时将撤回旧的申请，是否继续？");
    
    form.addButton("§c§l取消", "textures/ui/cancel");
    form.addButton("§2§l替换为最新申请", "textures/menu_1/right");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 0) {
            openTeamApplyConfirm(pl, teamId, team);
            return;
        }
        
        if (id === 1) {
            submitApplication(pl, teamId, team);
        }
    });
}

/**
 * 提交申请（实际执行）
 */
function submitApplication(player, teamId, team) {
    addApplication(teamId, player);
    
    player.tell("§a[团队系统] §f已向团队 §e" + team.name + " §f发送入队申请，请等待管理员处理！");
    log("[MGTeam] 玩家 " + player.realName + " 向团队 " + team.name + " (ID: " + teamId + ") 发送了入队申请");
    
    openMainMenu(player);
}

/**
 * 创建团队前检查在线时长和现有申请（修改后：添加开关判断）
 */
function openCreateTeamCheck(player) {
    // 修改：添加 EnablePlaytimeCheck 开关判断
    if (EnablePlaytimeCheck) {
        const checkResult = checkPlaytimeRequirement(player);
        
        if (!checkResult.valid) {
            const form = mc.newSimpleForm();
            
            form.setTitle("§l【团队系统】");
            form.setContent("§c§l在线时长不足，无法创建团队！\n\n§e你当前的在线时长：§f" + checkResult.current + " 分钟\n§e使用团队功能需要的在线时长：§f" + checkResult.required + " 分钟\n\n§7请继续在线游戏积累时长后再试。");
            
            form.addButton("§l返回", "textures/menu_1/lastpage");
            
            player.sendForm(form, (pl, id, reason) => {
                if (id === null || id === 0) {
                    openMainMenu(pl);
                    return;
                }
            });
            return;
        }
    }
    
    const pendingTeamId = hasPendingApplication(player.xuid);
    if (pendingTeamId) {
        const pendingTeam = teamData[pendingTeamId];
        openCreateTeamWithPendingConfirm(player, pendingTeamId, pendingTeam);
        return;
    }
    
    openCreateTeamMenu(player);
}

/**
 * 打开创建团队确认（存在未处理申请时）
 */
function openCreateTeamWithPendingConfirm(player, pendingTeamId, pendingTeam) {
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【团队系统】");
    form.setContent("§e存在未处理的团队加入申请！\n\n§7当前申请加入的团队：§f" + (pendingTeam ? pendingTeam.name : "未知团队") + "\n§7团队ID：§f" + pendingTeamId + "\n\n§c如果创建新团队，将自动撤回已发送的申请，是否继续？");
    
    form.addButton("§c§l取消", "textures/ui/cancel");
    form.addButton("§2§l确认并创建", "textures/menu_1/right");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 0) {
            openMainMenu(pl);
            return;
        }
        
        if (id === 1) {
            removePlayerAllApplications(pl.xuid);
            pl.tell("§a[团队系统] §f已撤回之前的团队加入申请");
            openCreateTeamMenu(pl);
        }
    });
}

/**
 * 打开创建团队菜单（修改后：使用配置变量显示费用）
 */
function openCreateTeamMenu(player) {
    const playerMoney = player.getMoney();
    
    const form = mc.newCustomForm();
    
    form.setTitle("§l【团队系统】");
    // 修改：使用 CreateTeamCost 和 moneyname 变量
    form.addLabel("§e创建或加入团队后，你将可以使用：\n\n• 与团队成员共享无数量上限的传送点\n• 团队成员间免同意互传\n• 团队积金自动垫付消费\n• 团队专属留言板\n\n§e§l创建费用：§c" + CreateTeamCost.toLocaleString() + " §7" + moneyname + "\n§e§l我的余额：§f" + playerMoney.toLocaleString() + " §7" + moneyname + "\n");
    form.addInput("§7团队名称", "请输入团队名称（2-10个字符）", "");
    form.addLabel("§8• 团队ID将由系统自动生成\n§8• 你将成为团队管理员\n§8• 创建后可通过团队ID邀请其他玩家\n§8• §c创建费用将从你的账户扣除");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openMainMenu(pl);
            return;
        }
        
        const teamName = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        if (!teamName || teamName.length < 2 || teamName.length > 10) {
            openAlertMenu(pl, "§c团队名称必须为2-10个字符！", () => {
                openCreateTeamMenu(pl);
            });
            return;
        }
        
        for (let id in teamData) {
            if (teamData[id].name === teamName) {
                openAlertMenu(pl, "§c已存在同名团队，请更换名称！", () => {
                    openCreateTeamMenu(pl);
                });
                return;
            }
        }
        
        const currentMoney = pl.getMoney();
        // 修改：使用 CreateTeamCost 变量
        const createCost = CreateTeamCost;
        
        if (currentMoney < createCost) {
            // 修改：使用 moneyname 变量
            openAlertMenu(pl, "§c余额不足！\n\n§e创建团队需要：§c" + createCost.toLocaleString() + " §7" + moneyname + "\n§e我的余额：§f" + currentMoney.toLocaleString() + " §7" + moneyname + "\n§e差额：§c" + (createCost - currentMoney).toLocaleString() + " §7" + moneyname, () => {
                openMainMenu(pl);
            });
            return;
        }
        
        openCreateTeamConfirmMenu(pl, teamName, createCost);
    });
}
/**
 * 打开创建团队确认菜单（修改后：使用配置变量）
 */
function openCreateTeamConfirmMenu(player, teamName, cost) {
    const playerMoney = player.getMoney();
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【团队系统】");
    
    let content = "§e请确认创建团队信息：\n\n";
    content += "§e§l团队名称：§f" + teamName + "\n";
    // 修改：使用 moneyname 变量
    content += "§e§l创建费用：§c" + cost.toLocaleString() + " §7" + moneyname + "\n";
    content += "§e§l当前余额：§f" + playerMoney.toLocaleString() + " §7" + moneyname + "\n";
    content += "§e§l扣除后余额：§f" + (playerMoney - cost).toLocaleString() + " §7" + moneyname + "\n\n";
    content += "§c§l注意：创建费用将从你的账户中立即扣除！\n";
    content += "§c此操作不可撤销，是否确认创建？";
    
    form.setContent(content);
    form.addButton("§c§l取消", "textures/ui/cancel");
    form.addButton("§2§l确认创建", "textures/menu_1/right");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 0) {
            openCreateTeamMenu(pl);
            return;
        }
        
        if (id === 1) {
            executeCreateTeam(pl, teamName, cost);
        }
    });
}
/**
 * 执行创建团队（修改后：使用配置变量显示）
 */
function executeCreateTeam(player, teamName, cost) {
    const currentMoney = player.getMoney();
    if (currentMoney < cost) {
        // 修改：使用 moneyname 变量
        openAlertMenu(player, "§c余额不足！创建失败。\n§e请确保你有足够的" + moneyname + "。", () => {
            openMainMenu(player);
        });
        return;
    }
    
    const deductSuccess = player.reduceMoney(cost);
    if (!deductSuccess) {
        openAlertMenu(player, "§c扣除货币失败！请重试或联系管理员。", () => {
            openMainMenu(player);
        });
        return;
    }
    
    const teamId = generateTeamId();
    
    teamData[teamId] = {
        name: teamName,
        operators: [{
            xuid: player.xuid,
            name: player.realName
        }],
        members: [],
        membersapplications: [],
        funds: 0,
        activity: 0,
        createdAt: new Date().toISOString(),
        notice: "",
        isPublic: true,
        allowFriendlyFire: true
    };
    
    if (!messageData[teamId]) {
        messageData[teamId] = [];
    }
    
    saveData();
    saveMessageData();
    
    const remainingMoney = player.getMoney();
    player.tell("§a§l[团队系统] §f团队 §e" + teamName + " §f创建成功！");
    player.tell("§a§l[团队系统] §f团队ID：§e" + teamId + " §f，请妥善保管！");
    // 修改：使用 moneyname 变量
    player.tell("§c§l[团队系统] §f已扣除创建费用 §c" + cost.toLocaleString() + " §f" + moneyname);
    player.tell("§a§l[团队系统] §f剩余余额：§e" + remainingMoney.toLocaleString() + " §f" + moneyname);
    
    // 修改：日志也使用 moneyname
    log("[MGTeam] 玩家 " + player.realName + " 创建团队 " + teamName + " (ID: " + teamId + ")，扣除费用 " + cost + " " + moneyname);
    
    openTeamDetail(player, teamId);
}

/**
 * 打开通用提示弹窗
 * @param player 玩家对象
 * @param message 提示消息（支持颜色代码）
 * @param callback 点击确定后的回调函数
 */
function openAlertMenu(player, message, callback) {
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【团队系统】");
    form.setContent(message);
    form.addButton("§2§l确定", "textures/menu_1/right");
    
    player.sendForm(form, (pl, id, reason) => {
        if (callback) {
            callback(pl);
        }
    });
}

/**
 * 打开管理申请页面
 */
function openManageApplications(player, teamId) {
    const team = teamData[teamId];
    const apps = getTeamApplications(teamId);
    
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【团队系统】");
    
    if (apps.length === 0) {
        form.setContent("§7当前没有待处理的入队申请。");
        form.addButton("§l返回", "textures/menu_1/lastpage");
        
        player.sendForm(form, (pl, id, reason) => {
            openTeamManageMenu(pl, teamId);
        });
        return;
    }
    
    form.setContent("§e请选择要处理的申请：\n§7共 " + apps.length + " 条待处理申请\n");
    
    for (let i = 0; i < apps.length; i++) {
        const app = apps[i];
        const date = new Date(app.AppliedAt);
        const timeStr = date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate() + " " + date.getHours() + ":" + (date.getMinutes() < 10 ? '0' : '') + date.getMinutes();
        form.addButton(getPlayerPlainDisplayName(app) + "\n§r" + timeStr, "textures/ui/icon_steve");
    }
    
    form.addButton("§l返回", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === apps.length) {
            openTeamManageMenu(pl, teamId);
            return;
        }
        
        openApplicationDetail(pl, teamId, apps[id]);
    });
}

/**
 * 打开申请处理详情
 */
function openApplicationDetail(player, teamId, application) {
    const team = teamData[teamId];
    const form = mc.newSimpleForm();
    
    const date = new Date(application.AppliedAt);
    const timeStr = date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate() + " " + date.getHours() + ":" + (date.getMinutes() < 10 ? '0' : '') + date.getMinutes();
    
    form.setTitle("§l【团队系统】");
    
    form.setContent("§e申请者信息：\n\n§e§l玩家名称：" + getPlayerDisplayName(application) +
        "\n§e§l玩家XUID：§f" + application.xuid +
        "\n§e§l申请时间：§f" + timeStr + "\n\n§7请选择处理方式：");
    
    form.addButton("§c§l忽略申请", "textures/ui/cancel");
    form.addButton("§2§l通过申请", "textures/menu_1/right");
    form.addButton("§l返回", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 2) {
            openManageApplications(pl, teamId);
            return;
        }
        
        if (id === 0) {
            removeApplication(teamId, application.xuid);
            pl.tell("§a[团队系统] §f已忽略 " + getPlayerPlainDisplayName(application) + " §f的入队申请");
            log("[MGTeam] 管理员 " + pl.realName + " 忽略了 " + (application.name || "未知玩家") + " 的申请");
            openManageApplications(pl, teamId);
        } else if (id === 1) {
            approveApplication(pl, teamId, application);
        }
    });
}

/**
 * 通过申请（将玩家加入团队）
 */
function approveApplication(player, teamId, application) {
    const team = teamData[teamId];
    
    const onlinePlayers = mc.getOnlinePlayers();
    let targetPlayer = null;
    for (let p of onlinePlayers) {
        if (p.xuid === application.xuid) {
            targetPlayer = p;
            break;
        }
    }
    
    if (getPlayerTeamByXuid(application.xuid)) {
        player.tell("§c[团队系统] §f该玩家已加入其他团队，无法通过申请！");
        removeApplication(teamId, application.xuid);
        openManageApplications(player, teamId);
        return;
    }
    
    if (!team.members) {
        team.members = [];
    }
    
    team.members.push({
        xuid: application.xuid,
        name: application.name
    });
    
    saveData();
    
    removeApplication(teamId, application.xuid);
    
    player.tell("§a[团队系统] §f已通过 §e" + application.name + " §f的入队申请！");
    log("[MGTeam] 管理员 " + player.realName + " 通过了 " + application.name + " 的申请，加入团队 " + team.name);
    
    if (targetPlayer) {
        targetPlayer.tell("§a[团队系统] §f你的入队申请已通过！欢迎加入 §e" + team.name + "§f！");
    }
    
    openManageApplications(player, teamId);
}

/**
 * 通过XUID获取玩家团队（辅助函数）
 */
function getPlayerTeamByXuid(xuid) {
    for (let teamId in teamData) {
        const team = teamData[teamId];
        if (team.operators && Array.isArray(team.operators)) {
            for (let op of team.operators) {
                if (op.xuid === xuid) {
                    return teamId;
                }
            }
        }
        if (team.members) {
            for (let member of team.members) {
                if (member.xuid === xuid) {
                    return teamId;
                }
            }
        }
    }
    return null;
}

/**
 * 通过RealName获取玩家团队（辅助函数）
 */
function getPlayerTeamByName(name) {
    for (let teamId in teamData) {
        const team = teamData[teamId];
        if (team.operators && Array.isArray(team.operators)) {
            for (let op of team.operators) {
                if (op.realName === name || op.name === name) {
                    return teamId;
                }
            }
        }
        if (team.members) {
            for (let member of team.members) {
                if (member.realName === name || member.name === name) {
                    return teamId;
                }
            }
        }
    }
    return null;
}

/**
 * 处理传送点命令
 */
function handleWarpCommand(player) {
    const teamId = getPlayerTeam(player);
    
    if (!teamId) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【传送锚点】");
        form.setContent("§c您不在任何一个团队中，请先加入团队后再使用该功能！");
        form.addButton("§l确定", "textures/menu_1/lastpage");
        player.sendForm(form, (pl, id, reason) => {
        });
        return;
    }
    
    openWarpMainMenu(player, teamId);
}

/**
 * 打开传送点主菜单
 */
function openWarpMainMenu(player, teamId) {
    const form = mc.newSimpleForm();
    
    form.setTitle("§l【传送锚点】");
    form.setContent("§7选择操作：");
    
    form.addButton("§e§l前往传送点", "textures/menu_1/gotohome");
    form.addButton("§2§l添加传送点", "textures/menu_1/addtmhome");
    form.addButton("§c§l移除传送点", "textures/menu_1/removetmhome");
    form.addButton("§l返回主菜单", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 3) {
            openMainMenu(pl);
            return;
        }
        
        switch (id) {
            case 0:
                openWarpTeleportMenu(pl, teamId);
                break;
            case 1:
                openAddWarpMenu(pl, teamId);
                break;
            case 2:
                openRemoveWarpMenu(pl, teamId);
                break;
        }
    });
}

/**
 * 打开添加传送点菜单
 */
function openAddWarpMenu(player, teamId) {
    const team = teamData[teamId];
    const warpPoints = team.warpPoints || {};
    
    const form = mc.newCustomForm();
    
    form.setTitle("§l【添加传送点】");
    form.addLabel("§e添加新的传送锚点\n\n§7将你当前的位置设为传送点，方便团队成员快速传送。");
    form.addInput("§7传送点名称", "例如：基地、矿洞、农场", "");
    
    player.sendForm(form, (pl, data, reason) => {
        if (!data) {
            openWarpMainMenu(pl, teamId);
            return;
        }
        
        const warpName = (data[1] !== undefined && data[1] !== null) ? String(data[1]).trim() : "";
        
        if (!warpName || warpName.length < 1 || warpName.length > 10) {
            openAlertMenu(pl, "§c传送点名称必须为1-10个字符！", () => {
                openAddWarpMenu(pl, teamId);
            });
            return;
        }
        
        if (warpPoints[warpName]) {
            openAlertMenu(pl, "§c传送点名称 §e" + warpName + " §c已存在，请使用其他名称！", () => {
                openAddWarpMenu(pl, teamId);
            });
            return;
        }
        
        const pos = pl.pos;
        const currentPos = {
            x: Math.floor(pos.x),
            y: Math.floor(pos.y),
            z: Math.floor(pos.z),
            dim: getPlayerDimId(pl)
        };
        
        openAddWarpConfirm(pl, teamId, warpName, currentPos);
    });
}

/**
 * 打开添加传送点确认菜单
 */
function openAddWarpConfirm(player, teamId, warpName, position) {
    const form = mc.newSimpleForm();
    
    const locationText = "§eX:§f" + position.x + " §eY:§f" + position.y + " §eZ:§f" + position.z + " §e维度:§f" + getDimName(position.dim);
    
    form.setTitle("§l【添加传送点】");
    form.setContent("§e请确认传送点信息：\n\n" +
        "§e§l名称：§f" + warpName + "\n" +
        "§e§l位置：§f" + locationText + "\n" +
        "§e§l创建者：§f" + player.realName + "\n\n" +
        "§c确认要创建此传送点？");
    
    form.addButton("§l取消", "textures/menu_1/lastpage");
    form.addButton("§2§l确认创建", "textures/menu_1/addtmhome");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 0) {
            openAddWarpMenu(pl, teamId);
            return;
        }
        
        if (id === 1) {
            executeAddWarp(pl, teamId, warpName, position);
        }
    });
}

/**
 * 执行添加传送点
 */
function executeAddWarp(player, teamId, warpName, position) {
    const team = teamData[teamId];
    
    if (!team.warpPoints) {
        team.warpPoints = {};
    }
    
    team.warpPoints[warpName] = {
        x: position.x,
        y: position.y,
        z: position.z,
        dim: position.dim,
        creatorXuid: player.xuid,
        creatorName: player.realName,
        createdAt: new Date().toISOString()
    };
    
    saveData();
    
    player.tell("§a[传送锚点] §f成功创建传送点 §e" + warpName + "§f！");
    log("[MGTeam] 玩家 " + player.realName + " 创建了团队 " + teamId + " 的传送点 " + warpName);
    
    openWarpMainMenu(player, teamId);
}

/**
 * 打开移除传送点菜单
 */
function openRemoveWarpMenu(player, teamId) {
    const team = teamData[teamId];
    const isOp = isTeamOperator(player, teamId);
    const warpPoints = team.warpPoints || {};
    const warpNames = Object.keys(warpPoints);
    
    if (warpNames.length === 0) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【传送锚点】");
        form.setContent("§c当前团队没有设置任何传送点！");
        form.addButton("§c§l返回", "textures/menu_1/lastpage");
        player.sendForm(form, (pl, id, reason) => {
            if (id === 0) {
                openWarpMainMenu(pl, teamId);
            }
        });
        return;
    }
    
    const removableWarps = [];
    for (let name of warpNames) {
        const wp = warpPoints[name];
        if (isOp || wp.creatorXuid === player.xuid) {
            removableWarps.push({
                name: name,
                warpPoint: wp
            });
        }
    }
    
    if (removableWarps.length === 0) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【传送锚点】");
        form.setContent("§c你没有权限移除任何传送点！\n\n§7普通成员只能移除自己创建的传送点。");
        form.addButton("§l返回", "textures/menu_1/lastpage");
        player.sendForm(form, (pl, id, reason) => {
            openWarpMainMenu(pl, teamId);
        });
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【移除传送点】");
    
    if (isOp) {
        form.setContent("§e选择要移除的传送点：\n§7§o（管理员可移除所有传送点）");
    } else {
        form.setContent("§e选择要移除的传送点：\n§7§o（成员只能移除自己创建的传送点）");
    }
    
    for (let warp of removableWarps) {
        const wp = warp.warpPoint;
        const dimName = getDimName(wp.dim);
        form.addButton("§l" + warp.name + "\n§r" + dimName + " | 创建者:" + getPlayerPlainDisplayName({name: wp.creatorName}), "textures/menu_1/tmtp");
    }
    
    form.addButton("§l返回", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === removableWarps.length) {
            openWarpMainMenu(pl, teamId);
            return;
        }
        
        if (id >= 0 && id < removableWarps.length) {
            const selectedWarp = removableWarps[id];
            openRemoveWarpConfirm(pl, teamId, selectedWarp.name, selectedWarp.warpPoint);
        }
    });
}

/**
 * 打开移除传送点确认菜单
 */
function openRemoveWarpConfirm(player, teamId, warpName, warpPoint) {
    const form = mc.newSimpleForm();
    
    const locationText = "§eX:§f" + warpPoint.x + " §eY:§f" + warpPoint.y + " §eZ:§f" + warpPoint.z + " §e维度:§f" + getDimName(warpPoint.dim);
    
    form.setTitle("§l【删除传送点】");
    
    form.setContent("§c确定要删除以下传送点？\n\n" +
        "§e§l名称：§f" + warpName + "\n" +
        "§e§l位置：§f" + locationText + "\n" +
        "§e§l创建者：" + getPlayerDisplayName({name: warpPoint.creatorName}) + "\n\n" +
        "§c此操作不可撤销！");
    
    form.addButton("§l取消", "textures/menu_1/lastpage");
    form.addButton("§c§l确认删除", "textures/menu_1/removetmhome");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === 0) {
            openRemoveWarpMenu(pl, teamId);
            return;
        }
        
        if (id === 1) {
            executeWarpDelete(pl, teamId, warpName);
        }
    });
}

/**
 * 执行删除传送点
 */
function executeWarpDelete(player, teamId, warpName) {
    const team = teamData[teamId];
    
    if (!team.warpPoints || !team.warpPoints[warpName]) {
        openAlertMenu(player, "§c传送点不存在或已被删除！", () => {
            openRemoveWarpMenu(player, teamId);
        });
        return;
    }
    
    delete team.warpPoints[warpName];
    saveData();
    
    player.tell("§a[传送锚点] §f已成功删除传送点 §e" + warpName + "§f！");
    log("[MGTeam] 玩家 " + player.realName + " 删除了团队 " + teamId + " 的传送点 " + warpName);
    
    openRemoveWarpMenu(player, teamId);
}

/**
 * 获取维度显示名称
 */
function getDimName(dimId) {
    switch (dimId) {
        case 0: return "主世界";
        case 1: return "下界";
        case 2: return "末地";
        default: return "未知维度(" + dimId + ")";
    }
}

/**
 * 打开传送点传送菜单
 */
function openWarpTeleportMenu(player, teamId) {
    const team = teamData[teamId];
    const warpPoints = team.warpPoints || {};
    const warpNames = Object.keys(warpPoints);
    
    if (warpNames.length === 0) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【传送锚点】");
        form.setContent("§c当前团队没有设置任何传送点！\n\n§7请先创建传送点。");
        form.addButton("§l返回", "textures/menu_1/lastpage");
        player.sendForm(form, (pl, id, reason) => {
            if (id === 0) {
                openWarpMainMenu(pl, teamId);
            }
        });
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【传送锚点】");
    form.setContent("§e选择传送点：");
    
    for (let name of warpNames) {
        const wp = warpPoints[name];
        const dimName = getDimName(wp.dim);
        form.addButton("§l" + name + "\n§r" + dimName + " | 创建者:" + getPlayerPlainDisplayName({name: wp.creatorName}), "textures/menu_1/tmtp");
    }
    
    form.addButton("§l返回", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === warpNames.length) {
            openWarpMainMenu(pl, teamId);
            return;
        }
        
        if (id >= 0 && id < warpNames.length) {
            const selectedName = warpNames[id];
            const wp = warpPoints[selectedName];
            teleportToWarp(pl, teamId, selectedName, wp);
        }
    });
}

/**
 * 传送到指定传送点
 */
function teleportToWarp(player, teamId, warpName, warpPoint) {
    const pos = mc.newFloatPos(warpPoint.x, warpPoint.y, warpPoint.z, warpPoint.dim);
    
    if (!pos) {
        openAlertMenu(player, "§c传送点坐标异常，无法传送！", () => {
            openWarpTeleportMenu(player, teamId);
        });
        return;
    }
    
    player.teleport(pos);
    player.tell("§a[传送锚点] §f已传送至 §e" + warpName + " §f！");
    log("[MGTeam] 玩家 " + player.realName + " 传送至团队 " + teamId + " 的传送点 " + warpName);
}

/**
 * 获取玩家当前维度ID
 */
function getPlayerDimId(player) {
    try {
        if (player.pos && player.pos.dimid !== undefined) {
            return player.pos.dimid;
        }
        return 0;
    } catch (e) {
        return 0;
    }
}

/**
 * 处理团队互传命令
 */
function handleTpaCommand(player) {
    const teamId = getPlayerTeam(player);
    
    if (!teamId) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【成员互传】");
        form.setContent("§c你不在任何一个团队中！");
        form.addButton("§l确定", "textures/menu_1/lastpage");
        player.sendForm(form, (pl, id, reason) => {});
        return;
    }
    
    openTpaMainMenu(player, teamId);
}

/**
 * 打开团队互传主菜单
 */
function openTpaMainMenu(player, teamId) {
    const team = teamData[teamId];
    const onlinePlayers = mc.getOnlinePlayers();
    const teamMembers = [];
    
    for (let p of onlinePlayers) {
        if (p.xuid === player.xuid) continue;
        
        const pTeamId = getPlayerTeam(p);
        if (pTeamId === teamId) {
            teamMembers.push(p);
        }
    }
    
    if (teamMembers.length === 0) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【成员互传】");
        form.setContent("§c当前团队没有其他在线玩家！");
        form.addButton("§l关闭", "textures/menu_1/lastpage");
        player.sendForm(form, (pl, id, reason) => {});
        return;
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【成员互传】");
    form.setContent("§7共 " + teamMembers.length + " 名队友在线。\n§e选择要传送的团队成员：");
    
    const playerDim = getPlayerDimId(player);
    const playerPos = player.pos;
    
    for (let teammate of teamMembers) {
        const name = teammate.realName;
        const teammateDim = getPlayerDimId(teammate);
        const teammatePos = teammate.pos;
        
        let line2 = "";
        if (teammateDim === playerDim) {
            const dx = teammatePos.x - playerPos.x;
            const dy = teammatePos.y - playerPos.y;
            const dz = teammatePos.z - playerPos.z;
            const distance = Math.sqrt(dx * dx + dy * dy + dz * dz).toFixed(1);
            
            const posStr = "X:" + Math.floor(teammatePos.x) + " Y:" + Math.floor(teammatePos.y) + " Z:" + Math.floor(teammatePos.z);
            line2 = posStr + " | 距离:" + distance + "米";
        } else {
            line2 = "§7所在维度:" + getDimName(teammateDim);
        }
        
        form.addButton("§l" + name + "\n§r" + line2, "textures/ui/icon_steve");
    }
    
    form.addButton("§l取消", "textures/menu_1/lastpage");
    
    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === teamMembers.length) {
            return;
        }
        
        if (id >= 0 && id < teamMembers.length) {
            const selectedPlayer = teamMembers[id];
            executeTeamTeleport(pl, teamId, selectedPlayer);
        }
    });
}

/**
 * 执行团队传送
 */
function executeTeamTeleport(player, teamId, targetPlayer) {
    const targetDim = getPlayerDimId(targetPlayer);
    const targetPos = targetPlayer.pos;
    
    const currentTargetTeam = getPlayerTeam(targetPlayer);
    if (currentTargetTeam !== teamId) {
        openAlertMenu(player, "§c目标玩家已离开团队，无法传送！", () => {
            openTpaMainMenu(player, teamId);
        });
        return;
    }
    
    const destPos = mc.newFloatPos(targetPos.x, targetPos.y, targetPos.z, targetDim);
    
    if (!destPos) {
        openAlertMenu(player, "§c目标位置异常，无法传送！", () => {
            openTpaMainMenu(player, teamId);
        });
        return;
    }
    
    const success = player.teleport(destPos);
    
    if (success) {
        player.sendToast("§a团队互传", "已传送至队友 §e" + targetPlayer.realName + " §a身边！");
        player.tell("§a[团队系统] §f已传送至 §e" + targetPlayer.realName + " §f身边！");
        
        targetPlayer.sendToast("§e团队互传", "队友 §a" + player.realName + " §e传送到了你身边！");
        
        log("[MGTeam] 玩家 " + player.realName + " 传送至队友 " + targetPlayer.realName + " 身边");
    } else {
        player.tell("§c[团队系统] §f传送失败，请重试！");
    }
}

/**
 * 打开团队公告编辑菜单（优化：提示换行符使用）
 */
function openNoticeEditMenu(player, teamId, defaultContent = "", isRetry = false) {
    const team = teamData[teamId];
    
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c只有团队管理员可以设置公告！", () => {
            openTeamManageMenu(player, teamId);
        });
        return;
    }
    
    let currentNotice = "";
    if (!isRetry && defaultContent === "") {
        currentNotice = team.notice || "";
    } else {
        currentNotice = defaultContent;
    }
    
    const form = mc.newCustomForm();
    form.setTitle("§l【团队公告设置】");
    
    let labelText = "§e编辑团队公告：\n\n";
    labelText += "§7• 公告会显示在主菜单和团队详情中。\n";
    labelText += "§7• 所有团队成员可见。\n";
    labelText += "§7• 使用颜色代码（如§a绿色§7）更改字体颜色。\n";
    labelText += "§7• 过度使用加粗字体可能使你的文本右侧超出菜单界面。\n";
    labelText += "§7• 使用 §f\\\\n §7换行。\n";
    labelText += "§7• 最多200字符。\n";
    
    form.addLabel(labelText);
    form.addInput("§7公告内容", "请输入公告内容...", currentNotice);
    
    player.sendForm(form, (pl, data, reason) => {
        if (!isTeamOperator(pl, teamId)) {
            openAlertMenu(pl, "§c你当前不是团队管理员！", () => {
                openTeamManageMenu(pl, teamId);
            });
            return;
        }
        
        if (!data) {
            openTeamManageMenu(pl, teamId);
            return;
        }
        
        const inputContent = (data[1] !== undefined && data[1] !== null) ? String(data[1]) : "";
        
        if (inputContent.length > 200) {
            openAlertMenu(pl, "§c公告内容过长！\n§7当前：" + inputContent.length + "字符\n§7限制：200字符", () => {
                openNoticeEditMenu(pl, teamId, inputContent, true);
            });
            return;
        }
        
        openNoticeConfirmMenu(pl, teamId, inputContent);
    });
}

/**
 * 打开公告确认和预览菜单（修复：预览换行显示）
 */
function openNoticeConfirmMenu(player, teamId, noticeContent) {
    const team = teamData[teamId];
    
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c你当前不是团队管理员！", () => {
            openTeamManageMenu(player, teamId);
        });
        return;
    }
    
    let previewText;
    if (noticeContent.trim() === "") {
        previewText = "§7（无公告）";
    } else {
        previewText = noticeContent.replace(/\\n/g, "\n").replace(/\n/g, "\n§f");
    }
    
    const form = mc.newSimpleForm();
    form.setTitle("§l【公告预览】");
    
    let content = "§e请确认公告内容：\n\n";
    content += "§e§l所属团队：§f" + team.name + "\n";
    content += "§e§l公告长度：§f" + noticeContent.length + "/200字符\n\n";
    content += "§e§l预览效果：§r\n";
    content += "§f━━━━━━━━━━━━━━\n";
    content += previewText + "\n";
    content += "§f━━━━━━━━━━━━━━\n\n";
    content += "§c确认要保存此公告吗？";
    
    form.setContent(content);
    form.addButton("§l返回修改", "textures/menu_1/lastpage");
    form.addButton("§2§l确认保存", "textures/menu_1/guanligonggao");
    
    player.sendForm(form, (pl, id, reason) => {
        if (!isTeamOperator(pl, teamId)) {
            openAlertMenu(pl, "§c你当前不是团队管理员！", () => {
                openTeamManageMenu(pl, teamId);
            });
            return;
        }
        
        if (id === null) {
            openNoticeEditMenu(pl, teamId, noticeContent, true);
            return;
        }
        
        if (id === 0) {
            openNoticeEditMenu(pl, teamId, noticeContent, true);
        } else if (id === 1) {
            saveTeamNotice(pl, teamId, noticeContent);
        }
    });
}

/**
 * 保存团队公告
 */
function saveTeamNotice(player, teamId, noticeContent) {
    const team = teamData[teamId];
    
    if (!isTeamOperator(player, teamId)) {
        openAlertMenu(player, "§c你当前不是团队管理员！", () => {
            openMainMenu(player);
        });
        return;
    }
    
    team.notice = noticeContent;
    
    saveData();
    
    if (noticeContent.trim() === "") {
        player.tell("§a[团队系统] §f团队公告已清空！");
        log("[MGTeam] 管理员 " + player.realName + " 清空了团队 " + teamId + " 的公告");
    } else {
        player.tell("§a[团队系统] §f团队公告已更新！");
        log("[MGTeam] 管理员 " + player.realName + " 更新了团队 " + teamId + " 的公告");
    }
    
    openMainMenu(player);
}

/**
 * 打开团队排行榜菜单（修改：现在按活跃度排序）
 */
function openTeamRankingMenu(player) {
    const publicTeams = [];

    for (let teamId in teamData) {
        const team = teamData[teamId];
        if (team.isPublic) {
            publicTeams.push({
                teamId: teamId,
                name: team.name,
                funds: team.funds || 0,
                activity: team.activity || 0,
                memberCount: (team.members ? team.members.length : 0) + (team.operators ? team.operators.length : 0)
            });
        }
    }

    if (publicTeams.length === 0) {
        const form = mc.newSimpleForm();
        form.setTitle("§l【团队排行榜】");
        form.setContent("§c当前没有公开的团队！\n\n§7所有团队目前都是私密状态，无法在排行榜中查找。");
        form.addButton("§l返回", "textures/menu_1/lastpage");
        player.sendForm(form, (pl, id, reason) => {
            openMainMenu(pl);
        });
        return;
    }

    publicTeams.sort((a, b) => {
        if (a.activity > 0 && b.activity === 0) return -1;
        if (b.activity > 0 && a.activity === 0) return 1;
        if (a.activity > 0 && b.activity > 0) return b.activity - a.activity;
        return b.funds - a.funds;
    });

    const form = mc.newSimpleForm();
    form.setTitle("§l【团队排行榜】");
    form.setContent("§e排行榜按活跃度与积金综合排序：\n§7共 " + publicTeams.length + " 个公开团队\n\n§7点击团队按钮查看详情并申请加入");

    for (let i = 0; i < publicTeams.length; i++) {
        const team = publicTeams[i];
        const rankIcon = getRankIcon(i);
        const buttonText = `§l${team.name}\n§r活跃度: §f${team.activity} §1| §r积金: §f${team.funds} §1| §r§f${team.memberCount}人`;
        form.addButton(buttonText, "textures/menu_1/tmtpa");
    }

    form.addButton("§l返回", "textures/menu_1/lastpage");

    player.sendForm(form, (pl, id, reason) => {
        if (id === null || id === publicTeams.length) {
            openMainMenu(pl);
            return;
        }

        if (id >= 0 && id < publicTeams.length) {
            const selectedTeam = publicTeams[id];
            const team = teamData[selectedTeam.teamId];
            openTeamApplyConfirm(pl, selectedTeam.teamId, team);
        }
    });
}
/**
 * 获取排名图标（辅助函数）
 */
function getRankIcon(rank) {
    if (rank === 0) return "§6🥇";
    if (rank === 1) return "§7🥈";
    if (rank === 2) return "§c🥉";
    return `§f${rank + 1}.`;
}

log("[MGTeam] MGteam团队系统 v0.6.0 已加载");
log("[MGTeam] 新增功能：团队活跃度系统、服务器管理员面板");
log("[MGTeam] 活跃度机制：玩家获得经验时团队活跃度+1，每小时所有团队活跃度-1（最低为0）");
log("[MGTeam] 使用 /tm 打开主菜单，/mgop 打开管理员面板");

function getPlayerOrgByXuid(xuid) {
    for (let teamId in teamData) {
        const team = teamData[teamId];
        if (team.operators && Array.isArray(team.operators)) {
            for (let op of team.operators) {
                if (op.xuid === xuid) {
                    return { teamId: teamId, team: team, role: 4 };
                }
            }
        }
        if (team.members && Array.isArray(team.members)) {
            for (let member of team.members) {
                if (member.xuid === xuid) {
                    return { teamId: teamId, team: team, role: 2 };
                }
            }
        }
    }
    return null;
}

function getPlayerAuxInTeam(xuid, teamId) {
    if (!teamData[teamId]) return -1;
    const team = teamData[teamId];

    if (team.operators && Array.isArray(team.operators)) {
        for (let op of team.operators) {
            if (op.xuid === xuid) {
                return 4;
            }
        }
    }

    if (team.members && Array.isArray(team.members)) {
        for (let member of team.members) {
            if (member.xuid === xuid) {
                return 2;
            }
        }
    }

    return -1;
}

ll.export(
    (xuid) => {
        const result = getPlayerOrgByXuid(xuid);
        if (!result) return null;
        return result.team.name;
    },
    'orgEX',
    'orgEX_getPlayerOrgName'
);

ll.export(
    (xuid) => {
        const result = getPlayerOrgByXuid(xuid);
        if (!result) return null;
        return result.teamId;
    },
    'orgEX',
    'orgEX_getPlayerOrgNum'
);

ll.export(
    (xuid) => {
        const result = getPlayerOrgByXuid(xuid);
        if (!result) return false;
        return result.role === 4;
    },
    'orgEX',
    'orgEX_playerIsOwner'
);

ll.export(
    (orgId) => {
        if (!teamData[orgId]) return null;
        return teamData[orgId].funds || 0;
    },
    'orgEX',
    'orgEX_orgGetMoney'
);

const moneyChangeBroadcaster = {};

function broadcastMoneyChange(orgId, change, reason) {
    if (!teamData[orgId]) return;

    // 记录流水账
    addFundLog(orgId, change, reason);

    const now = Date.now();
    if (!moneyChangeBroadcaster[orgId]) {
        moneyChangeBroadcaster[orgId] = {
            changes: [],
            timeout: null,
            originalMoney: teamData[orgId].funds
        };
    }

    moneyChangeBroadcaster[orgId].changes.push({ change, reason });

    if (moneyChangeBroadcaster[orgId].timeout) {
        clearTimeout(moneyChangeBroadcaster[orgId].timeout);
    }

    moneyChangeBroadcaster[orgId].timeout = setTimeout(() => {
        const broadcastData = moneyChangeBroadcaster[orgId];
        if (!broadcastData || broadcastData.changes.length === 0) return;

        const totalChange = broadcastData.changes.reduce((acc, c) => acc + c.change, 0);
        const finalMoney = broadcastData.originalMoney + totalChange;
        const originalMoney = broadcastData.originalMoney;

        let reasonText = "";
        if (broadcastData.changes.length > 1) {
            reasonText = "(多项变动)";
        } else if (broadcastData.changes[0].reason) {
            reasonText = `(${broadcastData.changes[0].reason})`;
        }

        const message = `§b[团队系统] §e原余额: §d${originalMoney} §f| §e变动: ${totalChange > 0 ? '§a+' : '§c'}${totalChange} §f| §e现余额: §d${finalMoney} ${reasonText}`;

        const members = teamData[orgId].members;
        for (const xuid in members) {
            const player = mc.getPlayer(xuid);
            if (player) {
                player.tell(message);
            }
        }

        delete moneyChangeBroadcaster[orgId];
    }, 3000);
}

ll.export(
    (orgId, count, reason) => {
        if (!teamData[orgId]) return false;
        const currentFunds = teamData[orgId].funds || 0;
        if (currentFunds + count < 0) return false;
        broadcastMoneyChange(orgId, count, reason);
        teamData[orgId].funds = currentFunds + count;
        saveData();
        return true;
    },
    'orgEX',
    'orgEX_orgAddMoney'
);

ll.export(
    (orgId) => {
        if (!teamData[orgId]) return null;
        return teamData[orgId].name;
    },
    'orgEX',
    'orgEX_getOrgName'
);

ll.export(
    (orgId, xuid) => {
        return getPlayerAuxInTeam(xuid, orgId);
    },
    'orgEX',
    'orgEXv2_getAux'
);

ll.export(
    (orgId) => {
        if (!teamData[orgId]) return [];
        const team = teamData[orgId];
        const members = [];

        if (team.operators && Array.isArray(team.operators)) {
            for (let op of team.operators) {
                members.push({ xuid: op.xuid, aux: 4 });
            }
        }

        if (team.members && Array.isArray(team.members)) {
            for (let member of team.members) {
                members.push({ xuid: member.xuid, aux: 2 });
            }
        }

        return members;
    },
    'orgEX',
    'orgEXv2_getAllMembers'
);

ll.export(
    (xuid) => {
        const result = [];
        for (let teamId in teamData) {
            const team = teamData[teamId];
            const aux = getPlayerAuxInTeam(xuid, teamId);
            if (aux >= 2) {
                result.push({
                    name: team.name,
                    size: (team.members ? team.members.length : 0) + (team.operators ? team.operators.length : 0),
                    orgID: teamId,
                    aux: aux
                });
            }
        }
        return result;
    },
    'orgEX',
    'orgEXv2_getAllOrgsByXuid'
);

ll.export(
    (orgId) => {
        if (!teamData[orgId]) return undefined;
        const team = teamData[orgId];
        return {
            id: orgId,
            name: team.name,
            size: (team.members ? team.members.length : 0) + (team.operators ? team.operators.length : 0),
            owner: team.operators && team.operators.length > 0 ? team.operators[0].xuid : null,
            data: {
                warplist: team.warpPoints ? Object.keys(team.warpPoints).map(name => ({
                    name: name,
                    pos: {
                        x: team.warpPoints[name].x,
                        y: team.warpPoints[name].y,
                        z: team.warpPoints[name].z,
                        dimid: team.warpPoints[name].dim
                    }
                })) : [],
                warplistLimit: 999,
                type: 'MGTeam',
                lobby: null,
                cost: 0,
                deposit: team.funds || 0,
                enableDepositTaking: true,
                enableJoinRequest: team.isPublic !== false
            }
        };
    },
    'orgEX',
    'orgEXv2_getOrgById'
);

ll.export(
    (name) => {
        for (let teamId in teamData) {
            if (teamData[teamId].name === name) {
                const team = teamData[teamId];
                return {
                    id: teamId,
                    name: team.name,
                    size: (team.members ? team.members.length : 0) + (team.operators ? team.operators.length : 0),
                    owner: team.operators && team.operators.length > 0 ? team.operators[0].xuid : null,
                    data: {
                        warplist: team.warpPoints ? Object.keys(team.warpPoints).map(name => ({
                            name: name,
                            pos: {
                                x: team.warpPoints[name].x,
                                y: team.warpPoints[name].y,
                                z: team.warpPoints[name].z,
                                dimid: team.warpPoints[name].dim
                            }
                        })) : [],
                        warplistLimit: 999,
                        type: 'MGTeam',
                        lobby: null,
                        cost: 0,
                        deposit: team.funds || 0,
                        enableDepositTaking: true,
                        enableJoinRequest: team.isPublic !== false
                    }
                };
            }
        }
        return undefined;
    },
    'orgEX',
    'orgEXv2_getOrgByName'
);

ll.export(
    (xuid) => {
        for (let teamId in teamData) {
            const team = teamData[teamId];
            if (team.operators && Array.isArray(team.operators)) {
                for (let op of team.operators) {
                    if (op.xuid === xuid) {
                        return {
                            id: teamId,
                            name: team.name,
                            size: (team.members ? team.members.length : 0) + (team.operators ? team.operators.length : 0),
                            owner: xuid,
                            data: {
                                warplist: team.warpPoints ? Object.keys(team.warpPoints).map(name => ({
                                    name: name,
                                    pos: {
                                        x: team.warpPoints[name].x,
                                        y: team.warpPoints[name].y,
                                        z: team.warpPoints[name].z,
                                        dimid: team.warpPoints[name].dim
                                    }
                                })) : [],
                                warplistLimit: 999,
                                type: 'MGTeam',
                                lobby: null,
                                cost: 0,
                                deposit: team.funds || 0,
                                enableDepositTaking: true,
                                enableJoinRequest: team.isPublic !== false
                            }
                        };
                    }
                }
            }
        }
        return undefined;
    },
    'orgEX',
    'orgEXv2_getOrgByOwner'
);

ll.export(
    () => {
        const result = [];
        for (let teamId in teamData) {
            const team = teamData[teamId];
            result.push({
                name: team.name,
                size: (team.members ? team.members.length : 0) + (team.operators ? team.operators.length : 0),
                orgID: teamId,
                aux: 4
            });
        }
        return result;
    },
    'orgEX',
    'orgEXv2_getAllOrg'
);

ll.export(
    (xuid) => {
        const result = getPlayerOrgByXuid(xuid);
        if (!result) return false;
        return result.role === 4;
    },
    'orgEX',
    'orgEXv2_IsOwner'
);

ll.export(
    (orgId) => {
        if (!teamData[orgId]) return null;
        return teamData[orgId].funds || 0;
    },
    'orgEX',
    'orgEXv2_getMoney'
);

ll.export(
    (orgId, count, reason) => {
        if (!teamData[orgId]) return false;
        const currentFunds = teamData[orgId].funds || 0;
        if (currentFunds + count < 0) return false;
        
        // 记录流水账
        addFundLog(orgId, count, reason || "外部插件调用");
        
        teamData[orgId].funds = currentFunds + count;
        saveData();
        return true;
    },
    'orgEX',
    'orgEXv2_pushMoney'
);

/**
 * 导出积金消费（垫付）相关接口
 */

// 1. 用于查询玩家是否开启团队积分消费（垫付）功能
ll.export(
    (xuid) => {
        return getFundConsumeStatus(xuid);
    },
    'MGteam',
    'MGteam_getFundConsumeStatus'
);

// 2. 用于开启/关闭玩家积分消费（垫付）功能
ll.export(
    (xuid, enabled) => {
        setFundConsumeStatus(xuid, !!enabled);
        return true;
    },
    'MGteam',
    'MGteam_setFundConsumeStatus'
);

// 3. 无视玩家目前的积分消费（垫付）开启状态，直接扣除玩家个人钱包（llmoney）
ll.export(
    (xuid, amount) => {
        const player = mc.getPlayer(xuid);
        if (!player) return false;
        
        // 更新监控器中的金额，防止 5 秒一次的定时器 checkPlayersMoneyChange 触发垫付补偿
        playerMoneyMonitor[xuid] = (playerMoneyMonitor[xuid] || player.getMoney()) - amount;
        
        return player.reduceMoney(amount);
    },
    'MGteam',
    'MGteam_reducePlayerMoneyDirect'
);