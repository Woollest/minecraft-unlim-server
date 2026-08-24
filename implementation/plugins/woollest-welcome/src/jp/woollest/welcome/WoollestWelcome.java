package jp.woollest.welcome;

import java.util.List;
import org.bukkit.ChatColor;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.plugin.java.JavaPlugin;

public final class WoollestWelcome extends JavaPlugin implements Listener {
    @Override
    public void onEnable() {
        saveDefaultConfig();
        getServer().getPluginManager().registerEvents(this, this);
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        boolean firstJoin = !player.hasPlayedBefore();
        long delay = Math.max(0, getConfig().getLong("delay-ticks", 20));
        getServer().getScheduler().runTaskLater(this, () -> {
            if (!player.isOnline()) {
                return;
            }
            List<String> messages = getConfig().getStringList("messages");
            for (String message : messages) {
                player.sendMessage(color(message.replace("{player}", player.getName())));
            }
            if (firstJoin) {
                for (String message : getConfig().getStringList("first-join-messages")) {
                    player.sendMessage(color(message.replace("{player}", player.getName())));
                }
            }
        }, delay);
    }

    private String color(String value) {
        return ChatColor.translateAlternateColorCodes('&', value);
    }
}
