package com.example.moviestream.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.moviestream.data.Movie
import com.example.moviestream.ui.CatalogState
import com.example.moviestream.ui.HomeRow
import com.example.moviestream.ui.MovieViewModel
import com.example.moviestream.ui.components.MovieArt
import com.example.moviestream.ui.components.PosterCard
import com.example.moviestream.ui.theme.Brand

@Composable
fun HomeScreen(
    viewModel: MovieViewModel,
    onOpenMovie: (Movie) -> Unit,
    onPlayMovie: (Movie) -> Unit,
    onOpenStreamUrl: () -> Unit,
) {
    val catalog by viewModel.catalog.collectAsStateWithLifecycle()
    val featured by viewModel.featured.collectAsStateWithLifecycle()
    val rows by viewModel.rows.collectAsStateWithLifecycle()
    val progress by viewModel.progress.collectAsStateWithLifecycle()
    val myList by viewModel.myListIds.collectAsStateWithLifecycle()

    when (val state = catalog) {
        CatalogState.Loading -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
        is CatalogState.Error -> Column(
            Modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(state.message, style = MaterialTheme.typography.bodyLarge)
            TextButton(onClick = viewModel::reload) { Text("Try again") }
        }
        is CatalogState.Ready -> LazyColumn(
            contentPadding = PaddingValues(bottom = 24.dp),
            modifier = Modifier.fillMaxSize(),
        ) {
            item {
                Box {
                    featured?.let { movie ->
                        Hero(
                            movie = movie,
                            inMyList = movie.id in myList,
                            onPlay = { onPlayMovie(movie) },
                            onInfo = { onOpenMovie(movie) },
                            onToggleList = { viewModel.toggleMyList(movie.id) },
                        )
                    }
                    TopBar(onOpenStreamUrl)
                }
            }
            items(rows, key = { it.title }) { row ->
                MovieRow(row, progress = { progress[it.id]?.fraction }, onOpenMovie = onOpenMovie)
            }
        }
    }
}

@Composable
private fun TopBar(onOpenStreamUrl: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "MOVIESTREAM",
            color = Brand,
            fontWeight = FontWeight.Black,
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.weight(1f),
        )
        IconButton(onClick = onOpenStreamUrl) {
            Icon(Icons.Filled.Link, contentDescription = "Play a stream URL")
        }
    }
}

@Composable
private fun Hero(
    movie: Movie,
    inMyList: Boolean,
    onPlay: () -> Unit,
    onInfo: () -> Unit,
    onToggleList: () -> Unit,
) {
    Box(Modifier.fillMaxWidth().height(480.dp)) {
        MovieArt(movie, Modifier.fillMaxSize(), showTitle = false)
        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        0f to Color.Black.copy(alpha = 0.55f),
                        0.35f to Color.Transparent,
                        1f to MaterialTheme.colorScheme.background,
                    ),
                ),
        )
        Column(
            Modifier
                .align(Alignment.BottomCenter)
                .padding(horizontal = 16.dp, vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(movie.title, style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold)
            Text(
                movie.genres.joinToString(" • "),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(onClick = onToggleList) {
                    Icon(if (inMyList) Icons.Filled.Check else Icons.Filled.Add, contentDescription = null)
                    Spacer(Modifier.width(4.dp))
                    Text("My List")
                }
                Button(
                    onClick = onPlay,
                    colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = Color.Black),
                ) {
                    Icon(Icons.Filled.PlayArrow, contentDescription = null)
                    Spacer(Modifier.width(4.dp))
                    Text("Play")
                }
                OutlinedButton(onClick = onInfo) {
                    Icon(Icons.Filled.Info, contentDescription = null)
                    Spacer(Modifier.width(4.dp))
                    Text("Info")
                }
            }
        }
    }
}

@Composable
private fun MovieRow(row: HomeRow, progress: (Movie) -> Float?, onOpenMovie: (Movie) -> Unit) {
    val showProgress = row.title == "Continue watching"
    Column(Modifier.padding(top = 16.dp)) {
        Text(
            row.title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        )
        LazyRow(
            contentPadding = PaddingValues(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(row.movies, key = { it.id }) { movie ->
                PosterCard(
                    movie = movie,
                    onClick = { onOpenMovie(movie) },
                    progress = if (showProgress) progress(movie) else null,
                )
            }
        }
    }
}
