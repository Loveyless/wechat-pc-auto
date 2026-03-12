use wechat_pc_auto_lib::adapter::ax_reader;

fn main() {
    println!("=== WeChat AX API 测试 (精确模式) ===\n");

    // 1. 当前会话名
    print!("1. 当前会话名: ");
    match ax_reader::read_active_chat_name() {
        Ok(name) => println!("✅ 「{}」", name),
        Err(e) => {
            println!("❌ {}", e);
            println!("\n请确保微信已启动、已登录，且已授权辅助功能权限。");
            return;
        }
    }

    // 1.5 群聊检测
    print!("1.5 群聊检测: ");
    match ax_reader::read_active_chat_member_count() {
        Ok(Some(count)) => println!("✅ 群聊 (成员数: {})", count),
        Ok(None) => println!("✅ 私聊 (无 current_chat_count_label)"),
        Err(e) => println!("❌ {}", e),
    }

    // 2. 聊天消息
    println!("\n2. 当前聊天消息 (chat_bubble_item_view):");
    match ax_reader::read_chat_messages() {
        Ok(messages) => {
            if messages.is_empty() {
                println!("   (当前没有聊天消息，可能未打开聊天窗口)");
            } else {
                for (i, msg) in messages.iter().enumerate() {
                    let display: String = msg.chars().take(80).collect();
                    let suffix = if msg.chars().count() > 80 { "..." } else { "" };
                    println!("   [{}] {}{}", i, display, suffix);
                }
            }
        }
        Err(e) => println!("   ❌ {}", e),
    }

    // 2.5 富消息正文
    println!("\n2.5 富消息正文 (read_chat_messages_rich):");
    match ax_reader::read_chat_messages_rich() {
        Ok(messages) => {
            if messages.is_empty() {
                println!("   (空)");
            } else {
                for (i, msg) in messages.iter().enumerate() {
                    let display: String = msg.content.chars().take(40).collect();
                    let suffix = if msg.content.chars().count() > 40 {
                        "..."
                    } else {
                        ""
                    };
                    println!("   [{}] content={}{}", i, display, suffix);
                }
            }
        }
        Err(e) => println!("   ❌ {}", e),
    }

    // 3. 最新消息
    println!("\n3. 最新消息:");
    match ax_reader::read_latest_message() {
        Ok(msg) => {
            if msg.is_empty() {
                println!("   (空)");
            } else {
                println!("   >>> {}", msg);
            }
        }
        Err(e) => println!("   ❌ {}", e),
    }

    // 4. 会话列表
    println!("\n4. 会话列表 (session_list):");
    match ax_reader::get_current_sessions() {
        Ok(sessions) => {
            if sessions.is_empty() {
                println!("   (空)");
            } else {
                for (i, s) in sessions.iter().enumerate() {
                    println!("   [{}] {}", i, s);
                }
            }
        }
        Err(e) => println!("   ❌ {}", e),
    }

    println!("\n=== 测试完成 ===");
}
