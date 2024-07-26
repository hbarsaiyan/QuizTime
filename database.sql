SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO';
SET @OLD_TIME_ZONE=@@TIME_ZONE;
SET TIME_ZONE='+00:00';

CREATE TABLE IF NOT EXISTS users (
    name varchar(50) NOT NULL,
    password varchar(255) NOT NULL,
    phone BIGINT(20) NOT NULL,
    dob DATE NOT NULL,
    email varchar(50) NOT NULL,
    gender char(1) NOT NULL,
    role char(1) NOT NULL,
    class_id int NULL,
    `user_image` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
    isActive char(1) NOT NULL,
    PRIMARY KEY (email, phone)
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS class_master (
    class_id int NOT NULL AUTO_INCREMENT,
    programme varchar(10) NOT NULL,
    branch varchar(10) NOT NULL,
    semester char(1) NOT NULL,
    PRIMARY KEY (class_id)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `questions` (
    `test_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `qid` varchar(25) COLLATE utf8mb4_unicode_ci NOT NULL,
    `q` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
    `a` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `b` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `c` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `d` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `ans` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
    `marks` int(25) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `studentans` (
  `email` varchar(50) DEFAULT NULL,
  `test_id` varchar(20) DEFAULT NULL,
  `qid` varchar(10) DEFAULT NULL,
  `ans` varchar(1) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `teststatus` (
  `email` varchar(50) DEFAULT NULL,
  `test_id` varchar(20) DEFAULT NULL,
  `time_left` time NOT NULL,
  `completed` tinyint(1) DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `testinfo` (
  `email` varchar(50) DEFAULT NULL,
  `test_id` varchar(20) DEFAULT NULL,
  `start` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `end` timestamp NOT NULL DEFAULT '2038-01-19 03:14:07',
  `duration` int(25) NOT NULL,
  `subject` varchar(20) DEFAULT NULL,
  `topic` varchar(30) DEFAULT NULL,
  `class_id` int NOT NULL
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `window_estimation_log` (
    `email` varchar(100) NOT NULL,
    `test_id` varchar(100) NOT NULL,
    `name` varchar(100) NOT NULL,
    `window_event` tinyint(2) NOT NULL,
    `transaction_log` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE = InnoDB DEFAULT CHARSET = latin1;

CREATE TABLE `proctoring_log` (
    `email` varchar(100) NOT NULL,
    `name` varchar(100) NOT NULL,
    `test_id` varchar(100) NOT NULL,
    `voice_db` int(100) DEFAULT '0',
    `img_log` longtext NOT NULL,
    `phone_detection` tinyint(2) NOT NULL,
    `person_status` tinyint(2) NOT NULL,
    `log_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE = InnoDB DEFAULT CHARSET = utf8;

UNLOCK TABLES;

SET TIME_ZONE=@OLD_TIME_ZONE;
SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;