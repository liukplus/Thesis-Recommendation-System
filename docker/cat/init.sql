-- ============================================
-- CAT (Central Application Tracking) Schema
-- For MySQL 5.7
-- Source: dianping/cat/script/CatApplication.sql
-- ============================================

CREATE DATABASE IF NOT EXISTS cat DEFAULT CHARACTER SET utf8mb4;
USE cat;

-- ── Reports ──────────────────────────────────

CREATE TABLE IF NOT EXISTS `hourlyreport` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(20) NOT NULL COMMENT 'report name: transaction, problem, event, etc.',
  `ip` varchar(50) NOT NULL COMMENT 'consumer machine ip',
  `domain` varchar(50) NOT NULL COMMENT 'project domain',
  `period` datetime NOT NULL COMMENT 'time period',
  `type` tinyint(4) NOT NULL COMMENT '1=xml, 2=json',
  `creation_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `period` (`period`,`domain`,`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `dailyreport` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(20) NOT NULL,
  `ip` varchar(50) NOT NULL,
  `domain` varchar(50) NOT NULL,
  `period` datetime NOT NULL,
  `type` tinyint(4) NOT NULL,
  `creation_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `period` (`period`,`domain`,`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `weeklyreport` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(20) NOT NULL,
  `ip` varchar(50) NOT NULL,
  `domain` varchar(50) NOT NULL,
  `period` datetime NOT NULL,
  `type` tinyint(4) NOT NULL,
  `creation_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `period` (`period`,`domain`,`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `monthreport` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(20) NOT NULL,
  `ip` varchar(50) NOT NULL,
  `domain` varchar(50) NOT NULL,
  `period` datetime NOT NULL,
  `type` tinyint(4) NOT NULL,
  `creation_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `period` (`period`,`domain`,`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `businessReport` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` tinyint(4) NOT NULL COMMENT '1=json, 2=xml',
  `name` varchar(20) NOT NULL,
  `ip` varchar(50) NOT NULL,
  `domain` varchar(50) NOT NULL,
  `period` datetime NOT NULL,
  `content` longblob COMMENT 'report content',
  `creation_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `period` (`period`,`domain`,`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 ROW_FORMAT=COMPRESSED;

-- ── Host & Project Info ──────────────────────

CREATE TABLE IF NOT EXISTS `hostinfo` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ip` varchar(50) NOT NULL COMMENT 'machine IP',
  `domain` varchar(200) NOT NULL COMMENT 'project name',
  `hostname` varchar(200) DEFAULT NULL COMMENT 'machine hostname',
  `creation_date` datetime NOT NULL,
  `last_modified_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ip` (`ip`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `project` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `domain` varchar(200) NOT NULL COMMENT 'project name',
  `cmdb_domain` varchar(200) DEFAULT NULL COMMENT 'CMDB project name',
  `level` int(11) DEFAULT NULL COMMENT 'project level',
  `bu` varchar(50) DEFAULT NULL COMMENT 'business unit',
  `cmdb_productline` varchar(50) DEFAULT NULL COMMENT 'CMDB product line',
  `owner` varchar(100) DEFAULT NULL COMMENT 'project owner',
  `email` varchar(200) DEFAULT NULL COMMENT 'owner email',
  `phone` varchar(50) DEFAULT NULL COMMENT 'owner phone',
  `creation_date` datetime NOT NULL,
  `modify_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `domain` (`domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tasks ────────────────────────────────────

CREATE TABLE IF NOT EXISTS `task` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `report_name` varchar(50) NOT NULL COMMENT 'report name',
  `report_domain` varchar(100) NOT NULL COMMENT 'report domain',
  `report_period` datetime NOT NULL COMMENT 'report period',
  `status` tinyint(4) NOT NULL COMMENT '1=doing, 2=done, 3=failed',
  `creation_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `report_period` (`report_period`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Config & Screen ──────────────────────────

CREATE TABLE IF NOT EXISTS `config` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL COMMENT 'config name',
  `content` longtext COMMENT 'config content (xml/json)',
  `creation_date` datetime NOT NULL,
  `modify_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `metric_graph` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `graph_id` int(11) NOT NULL,
  `name` varchar(200) NOT NULL COMMENT 'graph name',
  `title` varchar(200) NOT NULL COMMENT 'graph title',
  `type` tinyint(4) NOT NULL COMMENT '1=json, 2=xml',
  `content` longtext COMMENT 'graph content',
  `creation_date` datetime NOT NULL,
  `modify_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `graph_id` (`graph_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Insert default project ───────────────────

INSERT IGNORE INTO `project` (`domain`, `level`, `owner`, `email`, `creation_date`, `modify_date`)
VALUES ('thesis-recsys', 1, 'admin', 'admin@example.com', NOW(), NOW());