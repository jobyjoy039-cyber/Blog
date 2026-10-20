package com.example.moviestream.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.moviestream.data.Movie
import com.example.moviestream.ui.MovieViewModel
import com.example.moviestream.ui.components.PosterCard

@Composable
fun SearchScreen(viewModel: MovieViewModel, onOpenMovie: (Movie) -> Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    val catalog by viewModel.catalog.collectAsStateWithLifecycle()
    val results = remember(query, catalog) { viewModel.search(query) }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            singleLine = true,
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
            placeholder = { Text("Search titles, genres…") },
            modifier = Modifier.fillMaxWidth().padding(16.dp),
        )
        if (results.isEmpty()) {
            Text(
                "No matches for \"$query\"",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(16.dp),
            )
        } else {
            MovieGrid(results, onOpenMovie)
        }
    }
}

@Composable
fun MovieGrid(movies: List<Movie>, onOpenMovie: (Movie) -> Unit) {
    LazyVerticalGrid(
        columns = GridCells.Adaptive(110.dp),
        contentPadding = PaddingValues(16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        items(movies, key = { it.id }) { movie ->
            PosterCard(movie, onClick = { onOpenMovie(movie) }, modifier = Modifier.fillMaxWidth())
        }
    }
}
