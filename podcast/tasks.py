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

class Tagger(Task):
    def add_tags(self, enclosure):
        audio = MP3(enclosure.file.path, ID3=EasyID3)
        episode = enclosure.episode

        try:
            audio.add_tags(ID3=EasyID3)
        except MutagenError:
            pass

        audio['title'] = episode.title
        audio['album'] = episode.show.title
        audio['artist'] = ', '.join([author.get_full_name() for author in episode.author.all()])
        audio.save()

    def add_image(self, enclosure):
        audio = MP3(enclosure.file.path, ID3=ID3)
        episode = enclosure.episode
        picture = file(episode.show.image.path)

        try: 
            audio.add_tags()
        except MutagenError:
            pass
   
        audio.tags.add(
            APIC(
                encoding=3,
                type=3,
                desc='Cover',
                data=picture.read(),
                mime=mimetypes.guess_type( episode.show.image.path )
            )
        )
        audio.save()
        picture.close()

    def run(self, pk):
        enclosure = Enclosure.objects.get(pk=pk)
        if not enclosure.medium == 'Audio':
            return False
        self.add_tags(enclosure)
        self.add_image(enclosure)
        
def post_enclosure_save(sender, instance, created, *args, **kwargs):
    FillInEpisode().delay(instance.pk)
    Tagger().delay(instance.pk)
post_save.connect(post_enclosure_save, Enclosure)
