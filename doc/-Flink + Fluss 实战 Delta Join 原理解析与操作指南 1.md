---
标题: "-Flink + Fluss 实战: Delta Join 原理解析与操作指南"
链接: "https://mp.weixin.qq.com/s/yc-vPAmlfg-stAFKbbBwrA"
作者: "[[钟旭阳@阿里云]]"
创建时间: "2025-12-29T22:27:15+08:00"
摘要:
tags:
  - "clippings"
---
钟旭阳@阿里云 *2025年12月19日 18:03*

在使用 Flink SQL 进行实时数据处理的过程中，双流 Join 是非常常见的操作之一。典型的场景包括分析广告效果（曝光流订单流实时关联）、实时推荐（点击流和商品信息）等等。然而，双流 Join 需要在 状态 中维护两侧全量的历史数据，以确保计算结果的准确性。随着作业的持续运行，双流 Join 会逐渐带来一些问题：

- 运维层面
- 状态过大，开发者需要不断加大作业的资源才能维持较高的吞吐。
	- Checkpoint 易超时，导致作业不稳定、持续 Failover。
	- 状态是 Flink 内部产物，排查问题时，其内部数据难以探查。
- 开发层面
- Query 迭代修改后，状态难以复用，且重启回追代价高。

为了解决这些问题，Flink 社区在 2.1 引入了新的 Delta Join 算子，并在 2.2 对其进行了进一步的扩展。Delta Join 的核心思想是舍弃算子内本地状态冗余的数据存储，利用双向 Lookup Join 直接查询源表中的数据，而非查询状态中的数据，从而复用源表数据。Delta Join 结合流存储 Apache Fluss，在阿里巴巴淘宝天猫团队成功落地，并且对比双流 Join，拥有如下几个优势：

- 消除了将近 50 TB 的 双流 Join 状态
- 计算 CU 降低 10 倍
- 作业恢复速度提升 87 %
- Checkpoint 秒级完成

Flink Delta Join 介绍请参考：《Delta Join：为超大规模流处理实现计算与历史数据解耦》 https://developer.aliyun.com/article/1690558

**01**

**双流 Join 实现原理**

让我们先简单描述 Flink 双流 Join 的工作原理。

![图片](assets/flink-+-fluss-delta-join-1/c7851bcdbc278be37e934d53bb59b746_MD5.webp)

我们以处理左侧表来的 changelog 数据为例，流入的数据主要经过以下三个阶段。

1\. 通过 Join Key 查询对侧（即右侧）的状态，获取右侧历史上曾经流入该算子的全量数据 。

2\. 使用 Join 条件过滤查询得到的数据，并输出 。

3\. 将输入的本条数据，存入本侧（即左侧）的状态中，以供后续右侧的数据来临时，能正确的匹配数据。

之所以要把所有的数据用状态记录下来，是因为流计算是没有边界的，左侧数据和右侧数据匹配的时间点会存在时间差，即使一侧的数据延迟到达，也需要保证可以关联上另一侧的数据，最终输出。

双流 Join 的算法确保了数据的正确性，但是其状态会随着时间的推移而无限制增大，成为影响作业资源消耗和稳定性的关键因素。虽然目前已有 I nterval Join\[1\] 、 Lookup Join\[2\] 、 State TTL Hint\[3\] 等手段来缓解或解决该问题，但是均面向了特定的业务场景，牺牲了一定的功能（如 Lookup Join 舍弃了维表侧数据的更新追踪，State TTL Hint 放弃匹配超过 TTL 期限的数据）。

**02**

**Delta Join 技术原理**

从双流 Join 的原理上，我们可以观察到，状态里记录的全量数据，与源表中的数据基本相同，那么一个直观的想法是， 可以复用源表的数据来取代原有的状态 。Delta Join 正是基于这个思路，它利用了外部存储系统提供的索引能力，并不从状态中查找数据，而是直接对外部存储发出高效的、基于索引的数据查询，以获取匹配的记录。通过这种方式，Delta Join 消除了双流 Join 状态与外部系统之间冗余的数据存储。

![图片](assets/flink-+-fluss-delta-join-1/5846d90cb0d7ecb254925f0fcc6ecc52_MD5.webp)

## 理论推导

我们以两路输入为例，增量更新 Join 结果的公式为：

![图片](assets/flink-+-fluss-delta-join-1/c53c5af7657b60613e2efd88a7f5d296_MD5.webp)

其中， A 代表了左表的全量历史数据, 代表了左表中的增量数据。 B和 的定义与此类似。每当我们需要计算 Join 结果的增量部分时，我们只需要获取源表中从上次计算到当前时间之间新生成的数据，并查询对侧源表中的历史快照数据。因此我们需要：

1\. 感知源表的增量数据

2\. 访问源表历史快照数据

这对源表的物理存储引擎提出了很高的要求，存储引擎需要支持快照隔离，以确保强一致性语义。然而，目前存在以下几个问题：

1\. 目前只有有限的存储支持了快照的概念，例如 Paimon、 Iceberg 、Hudi 等等

2\. 快照生成的时间间隔为分钟级别，无法满足实时处理的要求

3\. 当指定快照查询数据时，快照可能会在存储系统中过期

考虑到上述这些问题，Flink 2.1 提出了一种 满足实时性要求 的、 最终一致性 的 Delta Join 方案。

## 最终一致性语义的 Delta Join

最终一致性语义的 Delta Join 并不要求源表的存储引擎支持快照。它总是去查询源表当前最新的数据。其对应的变种公式如下：

![图片](assets/flink-+-fluss-delta-join-1/a81520f2c4847a34efa3562aafcb6fec_MD5.webp)

和强一致性 Delta Join 相比，最终一致性 Delta Join 多出了一部分额外的中间结果 ， 因此，这种方法只能确保最终的结果是一致的。

以下是双流 Join 和两种语义的 Delta Join 的对比。

|  | 双流 Join | 强一致性 Delta Join | 最终一致性 Delta Join |
| --- | --- | --- | --- |
| 延迟 | 低 | 高 | 低 |
| 状态大小 | 大 | 小 | 小 |
| 状态内数据详情 | 两侧输入全量明细数据 | 上一次触发计算的源表快照id | 等待触发计算的异步队列 |
| 数据一致性 | 强一致性 | 强一致性 | 最终一致性 |

**03**

**Delta Join 算子实现**

为了提高算子的吞吐，在 Delta Join 算子中，分别引入了一个 TableAsyncExecutionController 组件和两个双侧完全相同的 DeltaJoinRunner 组件。

![图片](assets/flink-+-fluss-delta-join-1/ddf59107e489e95041f3bf00b6998334_MD5.webp)

## TableAsyncExecutionController 原理

该组件由 FLIP -519 Introduce async lookup key ordered mode\[4\] 引入，其严格限制相同 key 之间的数据必须串型执行，而允许不同 key 之间的数据并行处理，同时结合异步处理机制，大大提高了算子的吞吐能力。

该组件的运行原理如下：

![图片](assets/flink-+-fluss-delta-join-1/0b031044b24a22deeee3320f35af659b_MD5.webp)

TableAsyncExecutionController 在接收到数据后，按照 key 放入 BlockingBuffer 内不同 key 的队列里，然后通过 KeyAccountingUnit 检查该 key 是否被抢占、有对应的数据正在执行。如果 key 被抢占，直接返回；如果 key 未被抢占，则抢占该 key ，同时 poll 队列数据，放入 ActiveBuffer，交给后续计算逻辑处理，同时注册回调函数，在数据处理结束、输出后，在 KeyAccountingUnit 内释放该 key，去 BlockingBuffer 内拿下一条数据。

这套机制保证了相同 key 之间的数据是串行执行的，以避免出现分布式乱序问题。该机制在某种程度上是 FLIP -425 Asynchronous Execution Model\[5\] 的简化版本，感兴趣的可以另行研究。

在实际场景下，Delta Join 算子的吞吐会受到 BlockingBuffer 能允许的最大容量（各个 key 的队列大小之和）影响，当 BlockingBuffer 最大容量过小时，即使收到的每个 key 都不一样，也会由于无法充分利用异步并行的能力而导致吞吐较小。此时，可以适当调整下面的参数，来增大 BlockingBuffer 的最大容量。但如果设置的过大，BlockingBuffer 会占用比较高的内存，同时也可能会给外部存储带来较大的查询压力。

```cs
// 默认 100table.exec.async-lookup.buffer-capacity: 1000
```

我们可以通过监测 Delta Join 算子内以下几个 metric，来判断是否需要调整该参数。

- `aec_blocking_size` ：当前 BlockingBuffer 内被阻塞的所有 key 的队列大小之和。

该值越大，代表 join key 较为密集，考虑开启或增大 delta join cache；该值越小，但吞吐不佳的情况下，考虑增大 `table.exec.async-lookup.buffer-capacity` 的值。

- `aec_inflight_size` ：当前 ActiveBuffer 内正在执行计算的数据数量。

该值越大，代表当前同时请求外部存储集群的数据较多，存在请求堆积的情况，需要进一步查看外部存储系统是否存在异常，或查看是否有相关参数可以提高查询效率；该值越小，代表 join key 较为密集，考虑开启或增大 delta join cache。

![图片](assets/flink-+-fluss-delta-join-1/261d805d2c8c2b7ac79dfe06de1b6006_MD5.webp)

注：当 F luss 流存储的表作为 Delta Join 的源表时，你可以通过 Flink Table Hint\[6\] ，在 Fluss 表上配置以下这 些关键参数，来提高查询效率。

- `client.lookup.queue-size`
- `client.lookup.max-batch-size`
- `client.lookup.max-inflight-requests`
- `client.lookup.batch-timeout`

具体请参考 Fluss Connector Options\[7\]

**04**

**DeltaJoinRunner 原理**

DeltaJoinRunner 是负责执行 Lookup 的组件。由于 Delta Join 算子会处理两侧的数据，因此对于不同侧的数据，各有一个完全相同的 DeltaJoinRunner 负责 Lookup 对应表的数据。

想象一下，如果我们对每条数据都要去外部存储进行查询，对外部吞吐的压力会非常大，算子的吞吐性能完全取决于请求外部系统的吞吐。但如果用普通的 cache 来对 Lookup 的数据进行缓存，Lookup 目标表的数据更新消息将无法订阅。为此，我们引入了驱动侧仅构建、Lookup 侧仅更新的特殊 cache。

DeltaJoinRunner 组件的运行原理如下（图例是用于左侧输入流查询右侧源表的 DeltaJoinRunner），分别由 LocalCache 和 LookupFetcher 组成。

![图片](assets/flink-+-fluss-delta-join-1/ebbc2ed9c32bfb73b7c08a6c07c611a0_MD5.webp)

当左侧数据到达时，先去 LocalCache 查询是否有 cache。当有 cache 时，直接输出；当没有 cache 时，借助 LookupFetcher 通过右表的 index 查询右表的数据，然后将查询回来的数据在 LocalCache 中构建 cache，最后输出。

同时，右表的数据到达时，将会查看此 DeltaJoinRunner 中的 LocalCache 是否有 cache。如果没有cache，忽略更新；如果有 cache，更新 cache。

该 cache 机制一方面确保了在 join key 较为密集的场景，算子的吞吐能够得到巨大的提升，同时对外部存储也不会构成很大的查询压力；另一方面，确保了对侧最新的数据能够更新 cache，从而在后续的流程中能被正确地匹配上。

该 cache 是一个 LRU 的 cache，合理的设置该 cache 的大小是非常必要的。过小的 cache 大小将导致 ca che 的命中率受到影 响，过大的 cache 会占用较多的内存。我们可以通过下面的参数来分别调节左右两侧 cache 的大小，甚至是在每条数据 join key 都不相同、cache 基本无用时关闭 cache。

```cs
// 是否启用cache，默认为 truetable.exec.delta-join.cache-enabled: true// 设置用于缓存左表数据的cache大小，默认为 10000// 推荐在左表较小、或右流 join key 较为密集时，设置较大值table.exec.delta-join.left.cache-size: 10000// 设置用于缓存右表数据的cache大小，默认为 10000// 推荐在右表较小、或左流 join key 较为密集时，设置较大值table.exec.delta-join.right.cache-size: 10000
```

我们可以通过监测 Delta Join 算子上的 metric，来判断是否需要适当增加 cache 的大小。

- `deltaJoin_leftCache_hitRate`: 在右流查询左表的场景下，缓存左表数据的 cache 的命中率百分比。该值越高越好。
- `deltaJoin_rightCache_hitRate` ：在左流查询右表的场景下，缓存右表数据的 cache 的命中率百分比。该值越高越好。

![图片](assets/flink-+-fluss-delta-join-1/f483cc9e91568613af0dda63b4bce170_MD5.webp)

注：该图来自于“实战”章节 Nexmark q20 变种 query。右表 Auction 表每次都产生不同的id，故而 `deltaJoin_leftCache_hitRate` 的命中率始终为 0。

**05**

实战

我们借用 nexmark 数据集\[8\] 中 q20 的 query，略微修改后，作为本次实战的样例代码。

```sql
-- 获取包含相应拍卖信息的出价表INSERT INTO nexmark_q20SELECT    auction, bidder, price, channel, url, B.\`dateTime\`, B.extra,    itemName, description, initialBid, reserve, A.\`dateTime\`, expires, seller, category, A.extraFROM    bid AS B INNER JOIN auction AS A on B.auction = A.id;-- WHERE A.category = 10;
```

## 方式一：使用 Docker 环境测试

### 1\. 环境准备

（1）类 Unix 操作系统，如 Linux、Mac OS X

（2）内存建议至少 4 GB，磁盘建议至少 4 GB

### 2\. 下载 Docker 镜像

在命令行中， 运行如下命令安 装 Docker 测试镜像。

```apache
docker pull xuyangzzz/delta_join_example:1.0
```

运行如下命令运行该测试镜像，进入测试 docker container 的命令行。

```apache
docker run -p 8081:8081 -p 9123:9123 --name delta_join_example -it xuyangzzz/delta_join_example:1.0 bash
```

### 3\. 运行任务 SQL

```bash
# 运行 flink 和 fluss 集群./start-flink-fluss.sh
# 创建相关表和 delta join 作业./create-tables-and-run-delta-join.sh
```

此时，在宿主机 `localhost:8081` （或其他绑定的端口）即可查看 Flink UI 界面，可以看到此时 Delta Join 作业正在运行。

![图片](assets/flink-+-fluss-delta-join-1/dce93732e2fc7aed32902f689181f9d6_MD5.webp)

![图片](assets/flink-+-fluss-delta-join-1/280596226fd38ad08a4611e3189b0933_MD5.webp)

### 4\. 插入数据到源表

在测试 docker container 中执行下面的命令，为源表插入数据。

```bash
# 在源表插入数据./insert-data.sh
```

### 5\. 观察 Delta Join 作业

在宿主机 `localhost:8081` （或其他绑定的端口）的 flink-ui 界面，就可以看到 Delta Join 作业在正常消费数据 了。

![图片](assets/flink-+-fluss-delta-join-1/e03433796838dfbb82be93115e561edb_MD5.webp)

## 方式二：手工搭建环境测试

### 1\. 环境准备

#### （1）运行环境

a. 类 Unix 操作系统，如 Linux、Mac OS X

b. 内存建议至少 4 GB，磁盘建议至少 4 GB

c. Java 11 及以上版本，且将环境变量 `JAVA_HOME` 设置为 Java 的安装目录

#### （2）准备 Apache Flink 计算引擎

a. 下载

在 Apache Flink 官方下载网站\[9\] 下载最新的 Flink 2.2.0 版本，并解压。

b. 修改相关配置

修改./conf/config.yaml 文件，将 TaskManager numberOfTaskSlots 设置成 4 （默认为1）

![图片](assets/flink-+-fluss-delta-join-1/03f7856ce569bb3184f641cedb67999d_MD5.webp)

#### （3）准备 Apache Fluss 流存储引擎

在 Apache Fluss 官方下载网站 \[9\] 分别下载 Fluss 0.8 版本（并解压）和适配 Apahce Flink 2.1 的连接器。

![图片](assets/flink-+-fluss-delta-join-1/f012d4114b0702e3796cf797315c3623_MD5.webp)

#### （4）准备 Nexmark 源数据生成器

下载 Nexmark 项目\[10\] master 分支，在该项目根目录下，用 maven-3.8.6 版本执行以下的 maven 命令

```nginx
mvn clean install -DskipTests=true
```

在"./nexmark-flink/ target /" 文件夹下，将会生成 nexmark-flink-0.3-SNAPSHOT.jar 文件

### 2\. 服务启动

（1）启动 Flink

将 Fluss 适配 Flink 2.1 的连接器，以及 Nexmark 项目生成的 nexmark-flink-0.3-SNAPSHOT.jar 文件，放入 Flink 目录的./lib 目录下 。

参考 Flink 本地模式安装文档\[11\] ，在 Flink 目录中，执行下面的语句，启动本地 Standalone 集群。

```bash
## 请确保在 Flink 目录下执行该语句./bin/start-cluster.sh
```

检查 http://localhost:8081/#/overview 界面是否可正常访问。

（2）启动 Fluss

参考 Fluss 部署 Local Cluster 文档\[12\] ，在 Fluss 目录下，执行下面的语句，启动本地集群。

```bash
## 请确保在 Fluss 目录下执行该语句./bin/local-cluster.sh start
```

### 3\. 运行任务 SQL

#### （1）创建 Fluss 表

#### 将下面的 SQL 代码保存为“prepare\_table.sql”文件，其中定义了 2 张源表和 1 张结果表。

```sql
CREATE CATALOG fluss_catalogWITH (    'type'='fluss'    ,'bootstrap.servers'='localhost:9123');
USE CATALOG fluss_catalog;
CREATE DATABASE IF NOT EXISTS my_db;
USE my_db;
-- 创建左侧源表CREATE TABLE IF NOT EXISTS fluss_catalog.my_db.bid(    auction     BIGINT    ,bidder     BIGINT    ,price      BIGINT    ,channel    VARCHAR    ,url        VARCHAR    ,\`dateTime\` TIMESTAMP(3)    ,extra      VARCHAR    ,PRIMARY KEY (auction, bidder) NOT ENFORCED)WITH (-- fluss prefix lookup key，可用于 index    'bucket.key'='auction'-- Flink 2.2 中，delta join 仅支持消费不带 delete 操作的 cdc 源表    ,'table.delete.behavior'='IGNORE');
-- 创建右侧源表CREATE TABLE IF NOT EXISTS fluss_catalog.my_db.auction(    id           BIGINT    ,itemName    VARCHAR    ,description VARCHAR    ,initialBid  BIGINT    ,reserve     BIGINT    ,\`dateTime\`  TIMESTAMP(3)    ,expires     TIMESTAMP(3)    ,seller      BIGINT    ,category    BIGINT    ,extra       VARCHAR    ,PRIMARY KEY (id) NOT ENFORCED)WITH (-- Flink 2.2 中，delta join 仅支持消费不带 delete 操作的 cdc 源表    'table.delete.behavior'='IGNORE');
-- 创建 delta join 写入的结果表CREATE TABLE IF NOT EXISTS fluss_catalog.my_db.delta_join_sink(    auction           BIGINT    ,bidder           BIGINT    ,price            BIGINT    ,channel          VARCHAR    ,url              VARCHAR    ,bid_dateTime     TIMESTAMP(3)    ,bid_extra        VARCHAR    ,itemName         VARCHAR    ,description      VARCHAR    ,initialBid       BIGINT    ,reserve          BIGINT    ,auction_dateTime TIMESTAMP(3)    ,expires          TIMESTAMP(3)    ,seller           BIGINT    ,category         BIGINT    ,auction_extra    VARCHAR    ,PRIMARY KEY (auction, bidder) NOT ENFORCED);
```

在 Flink 目录下，执行下面的语句，创建持久化的表。

```bash
## 请确保在 Flink 目录下执行该语句## 注意：请将 ${your_path} 替换为 prepare_table.sql 实际所在的目录./bin/sql-client.sh -f ${your_path}/prepare_table.sql
```

#### （2）启动 Delta Join 作业

将下面的 SQL 代码保存为“run\_delta\_join.sql”文件，其中包含了可转化为 delta join 的 q20 变体查询。

```sql
CREATE CATALOG fluss_catalogWITH (    'type'='fluss'    ,'bootstrap.servers'='localhost:9123');
USE CATALOG fluss_catalog;
USE my_db;
INSERT INTO delta_join_sinkSELECT    auction    ,bidder    ,price    ,channel    ,url    ,B.\`dateTime\`    ,B.extra    ,itemName    ,description    ,initialBid    ,reserve    ,A.\`dateTime\`    ,expires    ,seller    ,category    ,A.extraFROM bid AS BINNER JOIN auction AS AON B.auction = A.id;
```

在 Flin k 目录下，执行下 面的语句，启动 delta join 作业。

```bash
## 请确保在 Flink 目录下执行该语句## 注意：请将 ${your_path} 替换为 run_delta_join.sql 实际所在的目录./bin/sql-client.sh -f ${your_path}/run_delta_join.sql
```

在 Flink UI 上，我们可以看到 Delta Join 作业正常跑起来了。

![图片](assets/flink-+-fluss-delta-join-1/9699d7da41d50fa2d0bf3d3866f61a92_MD5.webp)

### 4\. 插入数据到源表

将下面的 SQL 代码保存为“insert\_data.sql”文件，其中包含了向两张源表灌入 Nexmark 数据源产生模拟数据的作业。

```sql
CREATE CATALOG fluss_catalogWITH (    'type' = 'fluss'    ,'bootstrap.servers' = 'localhost:9123');
USE CATALOG fluss_catalog;
USE my_db;
-- nexmark 模拟数据源CREATE TEMPORARY TABLE datagen(    event_type  int    ,person ROW<        id BIGINT        ,name VARCHAR        ,emailAddress VARCHAR        ,creditCard VARCHAR        ,city VARCHAR        ,state VARCHAR        ,\`dateTime\` TIMESTAMP(3)        ,extra VARCHAR >    ,auction ROW<        id BIGINT        ,itemName VARCHAR        ,description VARCHAR        ,initialBid BIGINT        ,reserve BIGINT        ,\`dateTime\` TIMESTAMP(3)        ,expires TIMESTAMP(3)        ,seller BIGINT        ,category BIGINT        ,extra VARCHAR >    ,bid ROW<        auction BIGINT        ,bidder BIGINT        ,price BIGINT        ,channel VARCHAR        ,url VARCHAR        ,\`dateTime\` TIMESTAMP(3)        ,extra VARCHAR >    ,\`dateTime\` AS         CASE          WHEN event_type = 0 THEN person.\`dateTime\`          WHEN event_type = 1 THEN auction.\`dateTime\`          ELSE bid.\`dateTime\`        END    ,WATERMARK FOR \`dateTime\` AS \`dateTime\` - INTERVAL '4' SECOND)WITH (    'connector' = 'nexmark'    -- 下面两个参数为每秒数据生成速度    ,'first-event.rate' = '1000'    ,'next-event.rate' = '1000'    -- 生成的数据总条数，过大可能导致 OOM    ,'events.num' = '100000'    -- 下面三个参数为 Bid/Auction/Persion 三个数据的生成占比    ,'person.proportion' = '2'    ,'auction.proportion' = '24'    ,'bid.proportion' = '24');
CREATE TEMPORARY VIEW auction_viewAS SELECT    auction.id    ,auction.itemName    ,auction.description    ,auction.initialBid    ,auction.reserve    ,\`dateTime\`    ,auction.expires    ,auction.seller    ,auction.category    ,auction.extraFROM datagenWHERE event_type = 1;
CREATE TEMPORARY VIEW bid_viewAS SELECT    bid.auction    ,bid.bidder    ,bid.price    ,bid.channel    ,bid.url    ,\`dateTime\`    ,bid.extraFROM datagenWHERE event_type = 2;
INSERT INTO bidSELECT    *FROM bid_view;
INSERT INTO auctionSELECT    *FROM auction_view;
```

在 Flink 目录下，执行下面的语句，启动两个将 nexmark 模拟数据写入源表的作业。

```bash
## 请确保在 Flink 目录下执行该语句## 注意：请将 ${your_path} 替换为 insert_data.sql 实际所在的目录./bin/sql-client.sh -f ${your_path}/insert_data.sql
```

### 5\. 观察 Delta Join 作业

重新点击 Flink UI 上的 Delta Join 作业，可以看到 Delta Join 作业正常在消费数据了。

![图片](assets/flink-+-fluss-delta-join-1/0d44542979f189434eb03d43f629d777_MD5.webp)

**06**

**现状和未来工作**

目前 Delta Join 仍然在持续演进中，Flink 2.2 已经支持了一些常用的 SQL pattern ，具体可以 参考文档\[13\] 。

在未来，我们将会持续推进以下几个方向：

1\. 持续完善最终一致性 Delta Join

（1）支持 Left / Right Join

（2）支持消费 Delete

（3）支持级联 Delta Join

2\. 结合 Paimon/ Iceberg /Hudi 等支持快照的存储，支持分钟级的强一致性 Delta Join

参考链接：

\[1\] https://nightlies.apache.org/flink/flink-docs-master/docs/dev/table/sql/queries/joins/ [#interval](https://mp.weixin.qq.com/s/) \-joins

\[2\] https://nightlies.apache.org/flink/flink-docs-master/docs/dev/table/sql/queries/joins/ [#lookup](https://mp.weixin.qq.com/s/) \-join

\[3\] https://nightlies.apache.org/flink/flink-docs-master/docs/dev/table/sql/queries/hints/ [#state](https://mp.weixin.qq.com/s/) \-ttl-hints

\[4\] https://cwiki.apache.org/confluence/display/FLINK/FLIP-519:++Introduce+async+lookup+key+ordered+mode

\[5\] https://cwiki.apache.org/confluence/display/FLINK/FLIP-425%3A+Asynchronous+ Execution +Model

\[6\] https://nightlies.apache.org/flink/flink-docs-master/docs/dev/table/sql/queries/hints/ [#dynamic](https://mp.weixin.qq.com/s/) \-table- options

\[7\] https://fluss.apache.org/docs/engine-flink/options/ [#lookup](https://mp.weixin.qq.com/s/) \- options

\[8\] https://github.com/nexmark/nexmark/

\[9\] https://flink.apache.org/downloads/

\[10\] https://github.com/nexmark/nexmark/tree/master

\[11\] https://nightlies.apache.org/flink/flink-docs-release-2.2/zh/docs/try-flink/local\_installation/#%e6%ad%a5%e9%aa%a4-2%e5%90%af%e5%8a%a8%e9%9b%86%e7%be%a4

\[12\] https://fluss.apache.org/docs/install-deploy/deploying-local-cluster/

\[13\] https://nightlies.apache.org/flink/flink-docs-release-2.2/zh/docs/dev/table/tuning/#%E6%94%AF%E6%8C%81%E7%9A%84%E5%8A%9F%E8%83%BD%E5%92%8C%E9%99%90%E5%88%B6

▼ 「 Flink+Hologres 搭建实时数仓 」 ▼

复制下方链接或者扫描二维码

即可快速体验 “ 一体化的实时数仓联合解决方案”

了解活动详情： https://www.aliyun.com/solution/tech-solution/flink-hologres

![图片](assets/flink-+-fluss-delta-join-1/93cd4b6322c217e0ac94fe04820bb00f_MD5.webp)

---

---

▼ 关注「 **Apache Flink** 」 ▼

回复 FFA 2024 获取大会资料

![图片](assets/flink-+-fluss-delta-join-1/38abaac625c62b4a9de6581ad7dd2934_MD5.webp)

  
**点击「阅** **读** **原文** **」** **跳转 **阿里云实时计算 Flink～****

[阅读原文](https://mp.weixin.qq.com/s/)

继续滑动看下一个

Apache Flink

向上滑动看下一个