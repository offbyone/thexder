from curses import *
from math import *
from random import *
from sys import exit
from os import rename

import pygame
from pygame.locals import *

from . import data
from . import config

# for debugging: import pdb; pdb.set_trace()


###################################################
#
# This is a list of global constants and variables.
#
###################################################

#These are the screen dimensions (Constants!)
SCR_HEIGHT = 704
SCR_WIDTH = 880

#These are the level dimensions. There is no reason for me to have a fixed width. Also constant.
LVL_HEIGHT = 44

# This is the size of a tile in the file EGABITXX.BIN or TANBITXX.BIN
TILE_SIZE = 0x20

NUM_TILES = 8

TILE_HEIGHT = 0x08
TILE_WIDTH = 0x08

# This is the size of a pointer bit in EGAPTRXX.BIN
PTR_SIZE = 0x08

MAX_ENEMIES = 0x20

MAX_LEVELS = 16

#Which level are we editing?
curlvl = 1


COLORS = [pygame.Color(0,0,0), #Black
          pygame.Color(0xfa, 0x80, 0x72), #Salmon?
          pygame.Color(0,255,0), #Green
          pygame.Color(0,100,0), #Dark green
          pygame.Color(0xc7,0x61,0x14), #Brown?
          pygame.Color(100,0,0), #Dark red
          pygame.Color(255,255,100), #Yellow
          pygame.Color(255,0,255), #Magenta
          pygame.Color(0,0,100), #Dark Blue
          pygame.Color(100,0,75), #Dark purple
          pygame.Color(0,0,180), #Blue
          pygame.Color(100,255,255), #Cyan
          pygame.Color(40,40,40), #Dark Grey
          pygame.Color(255,50,255), #Magenta
          pygame.Color(130,130,160), #Blue-Gray
          pygame.Color(255,255,255)] #White

###############################################################################################
#
# Here are the classes that we need.
#
###############################################################################################

class level:
    """This will be where the class for storing level data."""

    def __init__(self,n):
        if n < 1 or n > 16:
            self.curlvl = 1
        else:
            self.curlvl = n
        self.open_lvl()

    def open_lvl(self):
        """
        This will open the level. This perhaps should be called in the __init__ procedure.
        """
        global LVL_HEIGHT
        dm = data.default_data_manager()
        level_name = "MAP{0:0>2}.BIN".format(self.curlvl)
        raw_level_data = dm.load_file(level_name)
        self.ldata = [[]]
        column_count = 0
        current_column = 0
        for c in raw_level_data:
            # If we've gone over/reached the level height, then we move over to the next column.
            if column_count >= LVL_HEIGHT:
                column_count = 0
                current_column += 1
                self.ldata.append([])

            c = ord(c)
            low = c % 16
            high = c >> 4
            # Two quick modifications: A high bit of 0 means 8 things in a row.
            # High bits of greater than (or equal to) 8 signify a monster.
            # There's also a slight issue here: This loses information when we do th bit about the high
            # bit being greater than 8. But there's no reason this has to be the case; we can store the data
            # in the ldata array, and use the tiles array when we actually display things.
            if high >= 8:
                self.ldata[current_column].append((high << 4) + low)
                column_count += 1
            else:
                if high == 0:
                    high = 8
                for i in range(0, high):
                    self.ldata[current_column].append(low)
                column_count += high

    def write_char(self, f, char, n):
        if n > 8:
            return False
        elif n == 8:
            n = 0
        if (char >> 4) > 0:
            f.write(chr(char))
        else:
            f.write(chr((n << 4) + char))
        return True

    def save(self):
        """
        This, not suprisingly, will save the file.
        It's a little unclear what happens a) to the junk at the end of the file
        b) to the fact that some bits are randomly stored otherwise.

        b) shouldn't matter, but a) might...
        """
        dm = data.default_data_manager()

        with dm.write("MAP{0:0>2}.BIN".format(self.curlvl)) as f:
            for i in range(0, self.width()):
                # Grab the first character from this column.
                last_char = self.tile(i,0)
                char_count = 1

                for j in range(1,self.height(i)):
                    # Grab the next character
                    char = self.tile(i,j)
                    if char != last_char or char_count >= 8:
                        # The character has changed, or we've gone over 8. Write the buffer to the file.
                        self.write_char(f,last_char,char_count)
                        char_count = 1
                    else:
                        # Increment the count.
                        char_count += 1
                    last_char = char

                # Write the last bit to the file.
                self.write_char(f,last_char,char_count)

        return True

    def tile(self,x,y):
        """
        This returns the tile at position x, y. These both start at 0.
        """
        if x < 0 or x >= len(self.ldata):
            return False
        if y < 0 or y >= len(self.ldata[x]):
            return False
        return self.ldata[x][y]

    def change_tile(self,x,y,new_tile):
        """
        This obviously changes the level data by making the tile at position (x,y) to be new_tile.

        The only thing that I need to consider is what to do about tiles with non-zero high bits.
        What should I do there? Leave them be for now?

        (x,y) are the position of the tile to change
        new_tile is (for now) a number between x0 and xF.
        """

        # First, check the bounds.
        if x < 0 or x >= self.width():
            return False
        if y < 0 or y >= self.height(x):
            return False

        self.ldata[x][y] = new_tile
        return True

    def width(self):
        return len(self.ldata)

    def height(self,column):
        if column >= self.width():
            return False
        return len(self.ldata[column])

#############################################################################################
#
# In the file BUGDBXX.BIN, the header information is as follows: each type of monster has two bytes
# per 0x40-length chunk. The five chunks are interpreted as follows:
#
# 0x0000 - health gain
# 0x0040 - enmax gain
# 0x0080 - points gain
# 0x00C0 - motion type:
#       00 - no motion.
#       01 - normal slow flying
#       02 - falling
#       03 - slow horizontal motion, no falling.
#       04 - rocket-type loopy motion.
#       05 - falling + slow horizontal motion.
#       06 - hidden (animation is different!), no moving once open.
#       07 - hidden (animation is different!), moves quickly once open.
#       08 - falls, moves randomly-ish.
#       09 - Seems to be about the same as 04?
#       0A - Quick up/down flying (ala bats)
#       0B - Weird jittery flying (also fast)
#       0C - diagonal fall, then no moving.
#       0D - same as 0C
#       0E - same as 0C
#       0F - same as 0C
#
# 0x0100 - health
#
# After this chunk, beginning at 0x0140, there are 12 bytes devoted to each monster.
# I will investigate further what they mean.
#
# Actually, it really seems that there are only 4 bytes. To be fair, not a lot must be encoded:
# Type, x-, y-positions.
#
# A typical one looks like ZWXY where
#   Z - Seems to be an offset into... something?
#       This seems to need to be a multiple of 4, starting at 80.
#       If it goes past the number of monsters (? How does it know?) then it gives junk.
#       If it is less than 80, then it seems to just be tiles.
#       If it is not a multiple of 4 then it gives animations, but they're offset. Also, the monsters
#       in such cases do not die (or not always?)
#   W - 0 always?
#   X - x position
#   Y - y position
#
#
# It is worth noting that it appears that the animation, thus, is hard-coded... sort of.
#
##############################################################################################

class enemy:
    """
    This should somehow be the class of a monster. It will consist of at least the animation,
    and also other data.
    """
    def __init__(self):
        pass

class animation:
    """
    This will be the class for an animation; it will consist of a collection of tiles.
    As usual, it takes as input a level number.
    n refers to which monster it should load, which will be some number
    between 0 and the largest number of monsters in that level.
    """
    def __init__(self, n, raw_tiles, pointers):
        global NUM_TILES, PTR_SIZE, MAX_ENEMIES

        if n < 0 or n >= MAX_ENEMIES:
            return False

        offsets = []

        for i in range(0, NUM_TILES):
            # This arcane formula just gets the offset numbers from the file.
            offset = [[ord(pointers[n * PTR_SIZE + i * 0x100]) + 0x0100 * ord(pointers[n * PTR_SIZE + i * 0x100 + 1]),
                       ord(pointers[n * PTR_SIZE + i * 0x100 + 2]) + 0x0100 * ord(pointers[n * PTR_SIZE + i * 0x100 + 3])],
                      [ord(pointers[n * PTR_SIZE + i * 0x100 + 4]) + 0x0100 * ord(pointers[n * PTR_SIZE + i * 0x100 + 5]),
                       ord(pointers[n * PTR_SIZE + i * 0x100 + 6]) + 0x0100 * ord(pointers[n * PTR_SIZE + i * 0x100 + 7])]]
            offsets.append(offset)

        # There are 8 tiles.
        self.tiles = []
        for i in range(0,len(offsets)):
            self.tiles.append(tile_array(raw_tiles,offsets[i]))


    def tile(self, n):
        if 0 <= n < len(self.tiles):
            return self.tiles[n]
        raise IOError


class tile_array:
    """
    This will be a class that contains a collection of tiles which fit into some array.
    """
    def __init__(self, raw_tile_string, offsets):
        """
        This should take as input a string which will be the raw tile data e.g. the contents
        of one of the files TANBITXX.BIN, as well as an array (of arrays) of offsets

        One change I might like to implement is to allow for offsets to just be an array as well,
        but for now this is easier.
        """
        global TILE_WIDTH, TILE_HEIGHT

        self.tiles = []
        for i in range(0, len(offsets)):
            self.tiles.append([])
            for j in range(0, len(offsets[i])):
                self.tiles[i].append(tile(raw_tile_string, offsets[i][j]))

        self.tiles_width = len(offsets[0])
        self.tiles_height = len(offsets)
        self.px_width = self.tiles_width * TILE_WIDTH
        self.px_height = self.tiles_height * TILE_HEIGHT

    def pixel(self, x, y):
        """
        This should treat the tile_array as a whole picture, and return the pixel at (x,y).
        """
        if 0 <= x < self.px_width and 0 <= y < self.px_height:
            tile_x = x / TILE_WIDTH
            tile_y = y / TILE_HEIGHT
            px_x = x % TILE_WIDTH
            px_y = y % TILE_HEIGHT
            return self.tile(tile_x,tile_y).pixel(px_x,px_y)
        return False

    def tile(self, x, y):
        """
        This should return the sub-tile which makes the picture up.
        """
        if 0 <= x < self.tiles_width and 0 <= y < self.tiles_height:
            return self.tiles[y][x]
        return False

    def width(self):
        return self.px_width

    def height(self):
        return self.px_height

class tile:
    """
    This will be the class for tile data, specifically an 8x8 tile.
    """
    def __init__(self, tiles, offset):
        """
        This has as input the level from which one should load the tile, and start, the offset.
        Then it will just read in the next few bytes.
        """
        global TILE_SIZE
        global TILE_HEIGHT

        cur_tile = tiles[offset : offset + TILE_SIZE]

        # Here we read in the string into an 8x8 array of pixel data.
        self.tile_data = []
        for i in range(0,TILE_HEIGHT):
            self.tile_data.append([])
            for j in range(0,TILE_WIDTH/2):
                # Get the high and low bits, separate them into separate pixels.
                ch = ord(cur_tile[i * 4 + j])
                low = ch % 0x10
                high = ch >> 4
                self.tile_data[i].extend([high, low])

        self.offset = offset



    def pixel(self,x,y):
        return self.tile_data[y][x]


    def tile_raw(self):
        return self.tile_data


    def width(self):
        # This should always return the number 8
        return len(self.tile_data[0])


    def height(self):
        # Same here.
        return len(self.tile_data)


##########################################################################################
#
# This displays what the tiles look like, four at a time. As it turns out, the tiles are
# all 16 x 16 arrays, and it seems that for levels 1--4 it uses tiles 0x20--0x2F
# while for levels 5--8 it uses tiles 0x10--0x1F. The mapping is exactly what you expect.
#
# Consequently, this should make it very easy to display the level!
#
##########################################################################################

def display_init(width, height):
    """
    This just sets up the pygame display.
    """
    pygame.init()
    pygame.key.set_repeat(120,30)
    return pygame.display.set_mode((width,height))

def draw_tiles(tiles):
    """
    This should take as input a set of tiles and return as output an array of game tiles. These
    will be pygame.Surface objects.
    """
    graphics = []
    for k in range(0, len(tiles)):
        graphics.append(draw_tile(tiles[k],2))

    graphics.append(pygame.Surface((16,16)))

    # Make the last one a blank one.
    pygame.draw.rect(graphics[len(tiles)],(180,0,0),(0,0,16,16),0)

    return graphics




def show_tiles(raw_tiles, raw_pointers):
    """
    This is intended to be a function for switching into the mode of showing tiles instead of the level.
    It needs to have w, the window, passed, as well as the current level to look at.

    Also, the raw tile data is passed. I'm not sure quite yet how I want to use it.
    """
    global MAX_ENEMIES, NUM_TILES

    monsters = []
    for i in range(0,MAX_ENEMIES):
        monsters.append(animation(i,raw_tiles,raw_pointers))

    cur_tile = 0
    cur_monster = 0


    pygame.init()
    pygame.key.set_repeat(120,60)
    screen = pygame.display.set_mode((320,320))


    going = True
    while going:
        # This is probably not too efficient (it re-renders the tile each time), but considering how few I need to
        # render each time (i.e. 1), it doesn't matter.
        screen.blit(draw_tile(monsters[cur_monster].tile(cur_tile)),(0,0))
        pygame.display.update()

        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                keys = pygame.key.get_pressed()

                if keys[K_UP]:
                    cur_monster -= 1
                    if cur_monster < 0:
                        cur_monster = 0
                elif keys[K_DOWN]:
                    cur_monster += 1
                    if cur_monster >= MAX_ENEMIES:
                        cur_monster = MAX_ENEMIES - 1
                elif keys[K_RIGHT]:
                    cur_tile += 1
                    if cur_tile >= NUM_TILES:
                        cur_tile = 0
                elif keys[K_LEFT]:
                    cur_tile -= 1
                    if cur_tile < 0:
                        cur_tile = NUM_TILES - 1
                else:
                    #pygame.display.quit()
                    going = False


def draw_tile(tile, size = 20):
    """
    This just draws a tile onto a new pygame.Surface object, and returns that object.

    The surface object it returns is automatically the correct size.
    """
    output = pygame.Surface((size * tile.width(), size * tile.height()))
    for i in range(0, tile.height()):
        for j in range(0, tile.width()):
            pygame.draw.rect(output,COLORS[tile.pixel(j,i)],(j*size,i*size,(j+1)*size,(i+1)*size),0)

    return output


def load_raw_tiles():
    """
    This, similar to the function below, will load all of the tiles from the file

    TNCHRS.BIN
    """
    global TILE_SIZE

    content = data.default_data_manager().load_file("TNCHRS.BIN")

    output = []

    for i in range(0, len(content) / TILE_SIZE ):
        output.append(tile(content,i * TILE_SIZE ))

    return output


def load_raw_animation_data():
    """
    This will just load the raw tiles from the TANBITXX.BIN files.
    This is needed due to the fact that some of the EGAPTRXX.BIN files have pointers
    which go past the end of the corresponding TANBIT file; my guess is that it then reads
    from the previous file.
    """
    global MAX_LEVELS
    output = []

    dm = data.default_data_manager()

    # Get the first set of tiles.
    output.append(dm.load_file("TANBIT01.BIN"))

    for i in range(1, MAX_LEVELS):
        try:
            # open the next file
            tiles = dm.load_file("TANBIT{0:0>2}.BIN".format(i+1))
            # if it isn't as long as the previous set of tiles, then we need to borrow from that set.
            if len(tiles) < len(output[-1]):
                tiles += output[-1][len(tiles):]
            output.append(tiles)
        except ValueError:
            # alternatively, if the file just doesn't exist (e.g. TANBIT03.BIN) then we just use the previous
            # tiles.
            output.append(output[-1])

    pointers = []
    for i in range(0, MAX_LEVELS):
        pointers.append(dm.load_file("EGAPTR{0:0>2}.BIN".format(i+1)))

    return (output, pointers)


#And here is the main function.
def main(w):
    global SCR_HEIGHT, SCR_WIDTH, LVL_HEIGHT
    global curlvl
    global tiles

    # Load all the tile data.
    (raw_tiles, raw_pointers) = load_raw_animation_data()
    lvl_tiles = load_raw_tiles()

    working_lvl = level(curlvl)

    lower_tile = 0x20
    upper_tile = 0x30

##########################
#
# This was a separate function before. For now it is included in main(), but this could change.
#
##########################

    tiles = lvl_tiles[lower_tile:upper_tile]

    screen = display_init(SCR_WIDTH, SCR_HEIGHT)

    graphics = draw_tiles(tiles)

    x_pos = 0
    y_pos = 0

    going = True
    while going:
        for j in range(0,SCR_WIDTH / 16):
            for i in range(0, SCR_HEIGHT / 16):
                cur_tile = working_lvl.tile(j + x_pos, i + y_pos)
                if cur_tile is False:
                    cur_tile = 0

                if cur_tile >> 4:
                    screen.blit(graphics[16],(j*16, i * 16))
                else:
                    screen.blit(graphics[cur_tile % 16], (j * 16, i * 16))

        pygame.display.update()

        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                keys = pygame.key.get_pressed()

                if keys[K_UP]:
                #    y_pos -= 1
                #    if y_pos < 0:
                #        y_pos = 0
                    x_pos -= 10
                elif keys[K_DOWN]:
                #    y_pos += 1
                #    if y_pos >= LVL_HEIGHT - SCR_HEIGHT:
                #        y_pos = LVL_HEIGHT - SCR_HEIGHT - 1
                    x_pos += 10
                elif keys[K_RIGHT]:
                    x_pos += 1
                elif keys[K_LEFT]:
                    x_pos -= 1
                elif keys[K_o]:
                    # This will open a new level. This is all old code and doesn't make sense.
                    new_lvl = prompt(w,"Which level would you like to open?")
                    try:
                        curlvl = int(new_lvl)
                    except ValueError:
                        alert(w,"Not a valid level number!")
                    else:
                        working_lvl = level(curlvl)
                        scr_x = 0
                        scr_y = 0

                    # Once we've loaded a level, we need to make sure that we are using the correct tiles.
                    # These seem to be hard-coded, so unfortunately this is all I can do.
                    if 1 <= curlvl <= 4:
                        lower_tile = 0x20
                        upper_tile = 0x30
                    elif 5 <= curlvl <= 7:
                        lower_tile = 0x10
                        upper_tile = 0x20
                    elif 8 <= curlvl <= 11:
                        lower_tile = 0x60
                        upper_tile = 0x70
                    elif 13 <= curlvl <= 15:
                        lower_tile = 0x70
                        upper_tile = 0x80
                    else:
                        lower_tile = 0x00
                        upper_tile = 0x10

                elif keys[K_t]:
                    # This will show the enemy tiles.
                    show_tiles(raw_tiles[curlvl-1], raw_pointers[curlvl - 1])
                else:
                    pygame.display.quit()
                    going = False

                if x_pos < 0:
                    x_pos = 0
                elif x_pos >= 512:
                    x_pos = 511

##############################


def cli():
    config.set_app_config_from_cli(config.base_argument_parser())
    return wrapper(main)

if __name__ == "__main__":
    cli()
