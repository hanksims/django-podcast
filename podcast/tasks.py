from celery.task import Task
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from mutagen.id3 import error as MutagenError
from mutagen.easyid3 import EasyID3

from podcast.models import Enclosure
from django.db.models.signals import post_save
import mimetypes

class FillInEpisode(Task):
    def run(self, pk):
        enclosure = Enclosure.objects.get(pk=pk)
        episode = enclosure.episode

        if not enclosure.medium == 'Audio':
            return False

        audio = MP3(enclosure.file.path)
        length = audio.info.length
        episode.minutes = int(length/60)
        episode.seconds = unicode( int(length % 60) )
        episode.save()        

class MutagenTagger(Task):

    def add_tags(self, audio_path=None, title=None, album=None, artist=None):
        audio = MP3(audio_path, ID3=EasyID3)

        # Mutagen requires this 
        try:
            audio.add_tags(ID3=EasyID3)
        except MutagenError:
            pass

        audio['title'] = title
        audio['album'] = album
        audio['artist'] = artist
        audio.save()

    def add_image(self, audio_path=None, image_path=None):
        audio = MP3(audio_path)
        image = file(image_path)

        try: 
            audio.add_tags()
        except MutagenError:
            pass
   
        audio.tags.add(
            APIC(
                encoding=3,
                type=3,
                desc='Cover',
                data=image.read(),
                mime=mimetypes.guess_type( image_path )
            )
        )
        audio.save()
        image.close()

    def run(self, 
        audio_path = None,
        image_path = None,
        title = None,
        album = None,
        artist = None
    ):
        if audio_path:
            self.add_tags(
                audio_path = audio_path,
                title = title,
                album = album,
                artist = artist
            )
            if image_path:
                self.add_image(
                    audio_path = audio_path,
                    image_path = image_path
                )

class EnclosureMutagenTagger(MutagenTagger):

    def run(self, pk):
        enclosure = Enclosure.objects.get(pk=pk)
        episode = enclosure.episode
        if not enclosure.medium == 'Audio':
            return False

        title = episode.title
        album = episode.show.title
        artist = ', '.join([author.get_full_name() for author in episode.author.all()])
        image_path = enclosure.episode.show.image.path
        audio_path = enclosure.file.path

        super(EnclosureMutagenTagger, self).run(
            audio_path = audio_path,
            image_path = image_path,
            title = title,
            album = album,
            artist = artist
        )
        
def post_enclosure_save(sender, instance, created, *args, **kwargs):
    FillInEpisode().delay(instance.pk)
    EnclosureMutagenTagger().delay(instance.pk)
post_save.connect(post_enclosure_save, Enclosure)
