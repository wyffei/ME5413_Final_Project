#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import rospy
from std_msgs.msg import String, Int32, Bool

class SecondFloorMinDigitEnter:
    def __init__(self):
        # ===== topics =====
        self.records_topic = rospy.get_param("~records_topic", "/percep/numbers")
        self.current_seen_digit_topic = rospy.get_param("~current_seen_digit_topic", "/percep/current_seen_digit")

        # 发布“进入房间”命令
        self.enter_room_topic = rospy.get_param("~enter_room_topic", "/second_floor/enter_room")
        # 可选：也发布一个简单布尔触发
        self.enter_trigger_topic = rospy.get_param("~enter_trigger_topic", "/second_floor/enter_room_trigger")

        # ===== behavior =====
        # 若最小值有多个数字并列，是否允许都触发
        self.allow_tie = rospy.get_param("~allow_tie", True)

        # 同一个数字的重复触发冷却
        self.same_digit_cooldown = rospy.get_param("~same_digit_cooldown", 2.0)

        # 是否忽略还没出现过的数字（count=0）
        # 二楼通常更合理的是 False：谁最少就找谁，0 也算最少
        self.ignore_zero_count = rospy.get_param("~ignore_zero_count", True)

        # 数字到房间号映射
        # 默认“数字几就进几号房”
        self.room_map = rospy.get_param("~room_map", {
            "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
            "5": 5, "6": 6, "7": 7, "8": 8, "9": 9
        })

        # ===== state =====
        self.counts = {i: 0 for i in range(10)}
        self.last_trigger_time = {i: -1e9 for i in range(10)}

        # ===== ROS =====
        self.records_sub = rospy.Subscriber(self.records_topic, String, self.records_callback, queue_size=1)
        self.current_seen_digit_sub = rospy.Subscriber(self.current_seen_digit_topic, Int32, self.current_seen_digit_callback, queue_size=1)

        self.enter_room_pub = rospy.Publisher(self.enter_room_topic, Int32, queue_size=1)
        self.enter_trigger_pub = rospy.Publisher(self.enter_trigger_topic, Bool, queue_size=1)

        rospy.loginfo("SecondFloorMinDigitEnter initialized.")

    def records_callback(self, msg):
        try:
            data = json.loads(msg.data)
            counts_raw = data.get("counts", {})
            new_counts = {i: 0 for i in range(10)}

            # 兼容 json 里 key 可能是字符串
            for k, v in counts_raw.items():
                try:
                    digit = int(k)
                    if 0 <= digit <= 9:
                        new_counts[digit] = int(v)
                except Exception:
                    pass

            self.counts = new_counts

        except Exception as e:
            rospy.logwarn_throttle(2.0, "Failed to parse %s: %s", self.records_topic, str(e))

    def get_min_count_digits(self):
        items = []
        for d in range(10):
            c = self.counts.get(d, 0)
            if self.ignore_zero_count and c == 0:
                continue
            items.append((d, c))

        if len(items) == 0:
            return []

        min_count = min(c for _, c in items)
        min_digits = [d for d, c in items if c == min_count]
        return min_digits

    def current_seen_digit_callback(self, msg):
        digit = int(msg.data)
        if digit < 0 or digit > 9:
            return

        min_digits = self.get_min_count_digits()
        if len(min_digits) == 0:
            return

        # 不允许并列时，只取最小集合里的最小数字
        if not self.allow_tie:
            min_digits = [min(min_digits)]

        if digit not in min_digits:
            rospy.loginfo_throttle(
                1.0,
                "Seen digit=%d, but current min digits=%s, counts=%s",
                digit, str(min_digits), str(self.counts)
            )
            return

        now = rospy.Time.now().to_sec()
        if now - self.last_trigger_time[digit] < self.same_digit_cooldown:
            return

        self.last_trigger_time[digit] = now

        room_id = int(self.room_map.get(str(digit), digit))

        self.enter_room_pub.publish(Int32(data=room_id))
        self.enter_trigger_pub.publish(Bool(data=True))

        rospy.logwarn(
            "Trigger enter room: seen digit=%d, room_id=%d, current counts=%s, min_digits=%s",
            digit, room_id, str(self.counts), str(min_digits)
        )


if __name__ == "__main__":
    rospy.init_node("second_floor_min_digit_enter")
    node = SecondFloorMinDigitEnter()
    rospy.spin()