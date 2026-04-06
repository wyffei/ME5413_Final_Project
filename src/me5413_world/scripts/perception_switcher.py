#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
perception_switcher.py

监听 cone trigger topic（默认 /cmd_unblock），
触发后：
  1. 关闭 box_counter_perception 节点
  2. 启动 perception_floor2.launch
"""

import subprocess
import threading
import rospy
from std_msgs.msg import Bool, String


class PerceptionSwitcher:
    def __init__(self):
        # ===== 参数 =====
        self.cone_trigger_topic = rospy.get_param("~cone_trigger_topic", "/cmd_unblock")
        self.box_counter_node_name = rospy.get_param("~box_counter_node_name", "/box_counter_perception")
        self.floor2_package = rospy.get_param("~floor2_package", "me5413_world")
        self.floor2_launch = rospy.get_param("~floor2_launch", "perception_floor2.launch")

        self._switched = False
        self._lock = threading.Lock()

        # 订阅 cone trigger
        # /cmd_unblock 可能是 Bool 或 String，这里用 String 兼容；
        # 如果是 Bool 类型，把下面两行换成 Bool 即可
        self._sub = rospy.Subscriber(
            self.cone_trigger_topic, Bool, self._trigger_cb, queue_size=1
        )

        rospy.loginfo(
            "[PerceptionSwitcher] Ready. Listening on '%s' to switch perception nodes.",
            self.cone_trigger_topic
        )

    def _trigger_cb(self, msg):
        # Bool 消息：只在 data=True 时触发
        if hasattr(msg, 'data') and not msg.data:
            return

        with self._lock:
            if self._switched:
                return  # 只切换一次
            self._switched = True

        rospy.logwarn("[PerceptionSwitcher] Cone trigger received! Switching perception nodes...")
        # 在独立线程中执行，避免阻塞回调
        t = threading.Thread(target=self._do_switch)
        t.daemon = True
        t.start()

    def _do_switch(self):
        # Step 1: 关闭 box_counter_perception
        rospy.loginfo("[PerceptionSwitcher] Killing node: %s", self.box_counter_node_name)
        try:
            result = subprocess.run(
                ["rosnode", "kill", self.box_counter_node_name],
                capture_output=True, text=True, timeout=10
            )
            rospy.loginfo("[PerceptionSwitcher] rosnode kill stdout: %s", result.stdout.strip())
            if result.returncode != 0:
                rospy.logwarn("[PerceptionSwitcher] rosnode kill stderr: %s", result.stderr.strip())
        except Exception as e:
            rospy.logwarn("[PerceptionSwitcher] Failed to kill box_counter_perception: %s", str(e))

        rospy.sleep(1.0)  # 等待节点完全退出

        # Step 2: 启动 perception_floor2.launch
        rospy.loginfo(
            "[PerceptionSwitcher] Launching %s/%s ...",
            self.floor2_package, self.floor2_launch
        )
        try:
            subprocess.Popen(
                ["roslaunch", self.floor2_package, self.floor2_launch],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            rospy.logwarn("[PerceptionSwitcher] perception_floor2 launched successfully.")
        except Exception as e:
            rospy.logerr("[PerceptionSwitcher] Failed to launch perception_floor2: %s", str(e))


if __name__ == "__main__":
    rospy.init_node("perception_switcher")
    node = PerceptionSwitcher()
    rospy.spin()