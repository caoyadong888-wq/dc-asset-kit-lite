# Daily data center inspection checklist

# 数据中心每日巡检表

Walk one hall. Mark **OK** or **NG** on every line. An NG row needs a remark and a severity: `high`, `medium`, or `low`. Do not leave a line blank.

巡视一个机房。每一行勾选 **OK** 或 **NG**。NG 必须写备注，并标明严重级别：`high`（高）、`medium`（中）、`low`（低）。不要留空行。

The matching CSV columns are `area`, `item_id`, `check_en`, `check_zh`, `OK`, `NG`, `severity`, `Remark`. Put `Y` in OK or NG. `scripts/inspection_report.py` reads that CSV.

对应 CSV 列为 `area`、`item_id`、`check_en`、`check_zh`、`OK`、`NG`、`severity`、`Remark`。在 OK 或 NG 列填写 `Y`。`scripts/inspection_report.py` 读取该 CSV。

Sample hall / 示例机房: rack A01, hosts `dc1-rack-a01-sw01`, `dc1-rack-a01-srv01`, `dc1-rack-a01-srv02`.

## Power / PDU

## 电源 / PDU

| ID | Check (EN) | 检查项 | OK | NG | Severity | Remark |
| --- | --- | --- | --- | --- | --- | --- |
| PDU-01 | PDU A feed indicator is normal | PDU A路指示灯正常 |  |  |  |  |
| PDU-02 | PDU B feed indicator is normal | PDU B路指示灯正常 |  |  |  |  |
| PDU-03 | Breakers are seated and labeled | 空开在位且有标签 |  |  |  |  |
| PDU-04 | No hot plugs, discoloration, or burning smell | 插头无过热、变色或焦糊味 |  |  |  |  |

## Cooling, temperature, and humidity

## 制冷、温度与湿度

| ID | Check (EN) | 检查项 | OK | NG | Severity | Remark |
| --- | --- | --- | --- | --- | --- | --- |
| CLG-01 | Cold-aisle temperature is within 18-27 C | 冷通道温度在 18-27 °C |  |  |  |  |
| CLG-02 | Hot-aisle temperature is within the site limit | 热通道温度未超过现场上限 |  |  |  |  |
| CLG-03 | Relative humidity is within 20-60 percent | 相对湿度在 20% 到 60% |  |  |  |  |
| CLG-04 | CRAC or in-row cooler is running with no alarm | 精密空调或列间空调运行且无告警 |  |  |  |  |

## UPS

## UPS

| ID | Check (EN) | 检查项 | OK | NG | Severity | Remark |
| --- | --- | --- | --- | --- | --- | --- |
| UPS-01 | UPS is online and not on battery | UPS 在线，未转入电池放电 |  |  |  |  |
| UPS-02 | No UPS alarm or fault lamp | UPS 无告警灯或故障灯 |  |  |  |  |
| UPS-03 | Load percent is within the site limit | 负载百分比未超过现场上限 |  |  |  |  |
| UPS-04 | Bypass switch is in the normal position | 旁路开关处于正常位置 |  |  |  |  |

## Rack doors and labels

## 机柜门与标签

| ID | Check (EN) | 检查项 | OK | NG | Severity | Remark |
| --- | --- | --- | --- | --- | --- | --- |
| RCK-01 | Front door is closed and latched | 前门关闭并锁好 |  |  |  |  |
| RCK-02 | Rear door is closed and latched | 后门关闭并锁好 |  |  |  |  |
| RCK-03 | Rack label matches the floor plan | 机柜标签与平面图一致 |  |  |  |  |
| RCK-04 | Asset labels are readable | 资产标签可读 |  |  |  |  |

## Cabling

## 布线

| ID | Check (EN) | 检查项 | OK | NG | Severity | Remark |
| --- | --- | --- | --- | --- | --- | --- |
| CAB-01 | Patch cords are seated at both ends | 跳线两端都插接到位 |  |  |  |  |
| CAB-02 | Bend radius looks within the cable spec | 弯曲半径看起来符合线缆规范 |  |  |  |  |
| CAB-03 | No unlabeled temporary cables | 没有未贴标的临时线缆 |  |  |  |  |
| CAB-04 | Cable managers are not overflowing | 理线器没有溢出 |  |  |  |  |

## LEDs and alarms

## 指示灯与告警

| ID | Check (EN) | 检查项 | OK | NG | Severity | Remark |
| --- | --- | --- | --- | --- | --- | --- |
| LED-01 | Switch system LED is green | 交换机系统灯为绿色 |  |  |  |  |
| LED-02 | No unexplained amber or red port LED | 没有说不清的琥珀色或红色端口灯 |  |  |  |  |
| LED-03 | Server health LED is normal | 服务器健康灯正常 |  |  |  |  |
| LED-04 | No active audible alarm | 没有持续的声音告警 |  |  |  |  |

## Fire suppression

## 消防

| ID | Check (EN) | 检查项 | OK | NG | Severity | Remark |
| --- | --- | --- | --- | --- | --- | --- |
| FIR-01 | Fire panel shows normal | 消防主机显示正常 |  |  |  |  |
| FIR-02 | No trouble or supervisory lamp | 没有故障灯或监管灯 |  |  |  |  |
| FIR-03 | Detectors and nozzles are unobstructed | 探测器和喷头没有被挡住 |  |  |  |  |
| FIR-04 | Manual release station seal is intact | 手动释放装置铅封完好 |  |  |  |  |

## Access log

## 进出记录

| ID | Check (EN) | 检查项 | OK | NG | Severity | Remark |
| --- | --- | --- | --- | --- | --- | --- |
| ACC-01 | Visitor log matches people on the floor | 访客记录和在场人员一致 |  |  |  |  |
| ACC-02 | Badge door is secured | 门禁门已关闭上锁 |  |  |  |  |
| ACC-03 | No door is held or propped open | 没有门被撑开或长开 |  |  |  |  |
| ACC-04 | Open work for this hall is noted | 本机房未完成的作业已写在备注里 |  |  |  |  |
