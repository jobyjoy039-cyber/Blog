package com.ugcstudio.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddCircle
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.ugcstudio.app.domain.usecase.SharedTextParser
import com.ugcstudio.app.ui.create.CreateScreen
import com.ugcstudio.app.ui.history.HistoryScreen
import com.ugcstudio.app.ui.job.JobScreen
import com.ugcstudio.app.ui.settings.SettingsScreen
import com.ugcstudio.app.ui.theme.UgcTheme
import dagger.hilt.android.AndroidEntryPoint

private data class Tab(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

private val TABS = listOf(
    Tab("create", "Create", Icons.Default.AddCircle),
    Tab("library", "Library", Icons.Default.VideoLibrary),
    Tab("settings", "Settings", Icons.Default.Settings),
)

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    private val sharedUrl = mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        handleShare(intent)
        setContent {
            UgcTheme {
                val nav = rememberNavController()
                val entry by nav.currentBackStackEntryAsState()
                val route = entry?.destination?.route
                Scaffold(bottomBar = {
                    if (route in TABS.map { it.route }) {
                        NavigationBar {
                            TABS.forEach { tab ->
                                NavigationBarItem(
                                    selected = route == tab.route,
                                    onClick = {
                                        nav.navigate(tab.route) {
                                            popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                            launchSingleTop = true
                                            restoreState = true
                                        }
                                    },
                                    icon = { Icon(tab.icon, null) },
                                    label = { Text(tab.label) },
                                )
                            }
                        }
                    }
                }) { pad ->
                    NavHost(nav, startDestination = "create", modifier = Modifier.padding(pad)) {
                        composable("create") {
                            val url by sharedUrl
                            CreateScreen(sharedUrl = url, onCreated = { id ->
                                sharedUrl.value = null
                                nav.navigate("job/$id")
                            })
                        }
                        composable("library") { HistoryScreen(onOpen = { nav.navigate("job/$it") }) }
                        composable("settings") { SettingsScreen() }
                        composable("job/{id}") { JobScreen(onBack = { nav.popBackStack() }) }
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleShare(intent)
    }

    private fun handleShare(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND) {
            SharedTextParser.firstUrl(intent.getStringExtra(Intent.EXTRA_TEXT))?.let { sharedUrl.value = it }
        }
    }
}
