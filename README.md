# hololive Dreams Scores

Renders holodori music scores to chart images (PNG). Takes a
[sonolus-level-converters](https://github.com/UntitledCharts/sonolus-level-converters)
`Score` object as input, with loaders included for holodori-style `.sus` files

## Installation

Install with pip：

```
pip install git+https://github.com/HolodoriDB/holodori-scores
```

## Usage

Render a score file from the command line：

```
python -m holodori.scores <xxx.sus> [--title ...] [--artist ...] [--difficulty ...] [--playlevel ...] [--jacket <path or url>] [-o <xxx.png>]
```

Here is an example of using it as a package to generate a chart image:

```python
from holodori.scores import ChartRenderer, load_sus

score, bar_lengths = load_sus('1.sus')

renderer = ChartRenderer(
    score,                # a sonolus_converters Score
    title='Tell Your World',
    difficulty='master',
    jacket='jacket.png',  # path or http(s) url, optional
    bar_lengths=bar_lengths,
)
renderer.render().save('1.png')  # render() returns a PIL.Image
```

Any `sonolus_converters` `Score` works as input. Only the note types the chart
view draws are supported: BPM changes, time scale changes (drawn as speed
lines), singles, slides, guides, and skill/fever markers.

## License

hololive Dreams Scores is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

hololive Dreams Scores is in no way affiliated with QualiArts, Cover, or hololive Dreams.
