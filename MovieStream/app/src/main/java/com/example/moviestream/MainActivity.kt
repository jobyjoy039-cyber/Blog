package com.example.moviestream

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.annotation.OptIn
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmarks
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.media3.common.util.UnstableApi
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.example.moviestream.player.PlayerActivity
import com.example.moviestream.ui.MovieViewModel
import com.example.moviestream.ui.components.StreamUrlDialog
import com.example.moviestream.ui.screens.DetailScreen
import com.example.moviestream.ui.screens.HomeScreen
import com.example.moviestream.ui.screens.MyListScreen
import com.example.moviestream.ui.screens.SearchScreen
import com.example.moviestream.ui.theme.MovieStreamTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MovieStreamTheme { MovieStreamApp() }
        }
    }
}

private enum class Tab(val route: String, val label: String, val icon: ImageVector) {
    Home("home", "Home", Icons.Filled.Home),
    Search("search", "Search", Icons.Filled.Search),
    MyList("mylist", "My List", Icons.Filled.Bookmarks),
}

@OptIn(UnstableApi::class)
@Composable
private fun MovieStreamApp(viewModel: MovieViewModel = viewModel()) {
    val context = LocalContext.current
    val navController = rememberNavController()
    val backStack by navController.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route
    var showUrlDialog by rememberSaveable { mutableStateOf(false) }

    val openMovie: (String) -> Unit = { id -> navController.navigate("movie/$id") }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        contentWindowInsets = WindowInsets(0),
        bottomBar = {
            if (Tab.entries.any { it.route == currentRoute }) {
                NavigationBar(containerColor = MaterialTheme.colorScheme.surfaceContainer) {
                    Tab.entries.forEach { tab ->
                        NavigationBarItem(
                            selected = currentRoute == tab.route,
                            onClick = {
                                navController.navigate(tab.route) {
                                    popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = null) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            NavHost(navController, startDestination = Tab.Home.route) {
                composable(Tab.Home.route) {
                    HomeScreen(
                        viewModel = viewModel,
                        onOpenMovie = { openMovie(it.id) },
                        onPlayMovie = { PlayerActivity.play(context, it) },
                        onOpenStreamUrl = { showUrlDialog = true },
                    )
                }
                composable(Tab.Search.route) {
                    SearchScreen(viewModel, onOpenMovie = { openMovie(it.id) })
                }
                composable(Tab.MyList.route) {
                    MyListScreen(viewModel, onOpenMovie = { openMovie(it.id) })
                }
                composable("movie/{id}") { entry ->
                    DetailScreen(
                        viewModel = viewModel,
                        movieId = entry.arguments?.getString("id").orEmpty(),
                        onBack = { navController.popBackStack() },
                        onPlay = { movie, fromStart -> PlayerActivity.play(context, movie, fromStart) },
                    )
                }
            }
        }
    }

    if (showUrlDialog) {
        StreamUrlDialog(
            onDismiss = { showUrlDialog = false },
            onPlay = { url ->
                showUrlDialog = false
                PlayerActivity.playUrl(context, url)
            },
        )
    }
}
