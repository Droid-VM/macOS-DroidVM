/* iig(DriverKit-427.100.5 Apr 30 2025 01:57:02) generated from IODMACommand.iig */

#undef	IIG_IMPLEMENTATION
#define	IIG_IMPLEMENTATION 	IODMACommand.iig

#if KERNEL
#include <libkern/c++/OSString.h>
#else
#include <DriverKit/DriverKit.h>
#endif /* KERNEL */
#include <DriverKit/IOReturn.h>
#include <DriverKit/IODMACommand.h>


#if __has_builtin(__builtin_load_member_function_pointer)
#define SimpleMemberFunctionCast(cfnty, self, func) (cfnty)__builtin_load_member_function_pointer(self, func)
#else
#define SimpleMemberFunctionCast(cfnty, self, func) OSMemberFunctionCast(cfnty, &(self), func)
#endif


struct IODMACommand_Create_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  device;
    uint64_t  options;
    IODMACommandSpecification  specification;
};
#pragma pack(4)
struct IODMACommand_Create_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t device__descriptor;
};
struct IODMACommand_Create_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t device__descriptor;
    IODMACommand_Create_Msg_Content content;
};
#pragma pack()
#define IODMACommand_Create_Msg_ObjRefs (2)

struct IODMACommand_Create_Rpl_Content
{
    IORPCMessage __hdr;
    OSObjectRef  command;
};
#pragma pack(4)
struct IODMACommand_Create_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t command__descriptor;
};
struct IODMACommand_Create_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t command__descriptor;
    IODMACommand_Create_Rpl_Content content;
};
#pragma pack()
#define IODMACommand_Create_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IODMACommand_Create_Msg * message;
#else /* KERNEL */
        const struct IODMACommand_Create_Msg_With_Content * message;
#endif /* KERNEL */
        struct IODMACommand_Create_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IODMACommand_Create_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IODMACommand_Create_Invocation;
struct IODMACommand_PrepareForDMA_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  memory;
    uint64_t  options;
    uint64_t  offset;
    uint64_t  length;
    unsigned int  segmentsCount;
};
#pragma pack(4)
struct IODMACommand_PrepareForDMA_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t memory__descriptor;
};
struct IODMACommand_PrepareForDMA_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t memory__descriptor;
    IODMACommand_PrepareForDMA_Msg_Content content;
};
#pragma pack()
#define IODMACommand_PrepareForDMA_Msg_ObjRefs (2)

struct IODMACommand_PrepareForDMA_Rpl_Content
{
    IORPCMessage __hdr;
    unsigned long long  flags;
    unsigned int  segmentsCount;
    IOAddressSegment *  segments;
#if !defined(__LP64__)
    uint32_t __segmentsPad;
#endif /* !defined(__LP64__) */
    IOAddressSegment __segments[32];
};
#pragma pack(4)
struct IODMACommand_PrepareForDMA_Rpl
{
    IORPCMessageMach           mach;
};
struct IODMACommand_PrepareForDMA_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IODMACommand_PrepareForDMA_Rpl_Content content;
};
#pragma pack()
#define IODMACommand_PrepareForDMA_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IODMACommand_PrepareForDMA_Msg * message;
#else /* KERNEL */
        const struct IODMACommand_PrepareForDMA_Msg_With_Content * message;
#endif /* KERNEL */
        struct IODMACommand_PrepareForDMA_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IODMACommand_PrepareForDMA_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IODMACommand_PrepareForDMA_Invocation;
struct IODMACommand_CompleteDMA_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    uint64_t  options;
};
#pragma pack(4)
struct IODMACommand_CompleteDMA_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IODMACommand_CompleteDMA_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IODMACommand_CompleteDMA_Msg_Content content;
};
#pragma pack()
#define IODMACommand_CompleteDMA_Msg_ObjRefs (1)

struct IODMACommand_CompleteDMA_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IODMACommand_CompleteDMA_Rpl
{
    IORPCMessageMach           mach;
};
struct IODMACommand_CompleteDMA_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IODMACommand_CompleteDMA_Rpl_Content content;
};
#pragma pack()
#define IODMACommand_CompleteDMA_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IODMACommand_CompleteDMA_Msg * message;
#else /* KERNEL */
        const struct IODMACommand_CompleteDMA_Msg_With_Content * message;
#endif /* KERNEL */
        struct IODMACommand_CompleteDMA_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IODMACommand_CompleteDMA_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IODMACommand_CompleteDMA_Invocation;
struct IODMACommand_GetPreparation_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
};
#pragma pack(4)
struct IODMACommand_GetPreparation_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IODMACommand_GetPreparation_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IODMACommand_GetPreparation_Msg_Content content;
};
#pragma pack()
#define IODMACommand_GetPreparation_Msg_ObjRefs (1)

struct IODMACommand_GetPreparation_Rpl_Content
{
    IORPCMessage __hdr;
    OSObjectRef  memory;
    unsigned long long  offset;
    unsigned long long  length;
};
#pragma pack(4)
struct IODMACommand_GetPreparation_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t memory__descriptor;
};
struct IODMACommand_GetPreparation_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t memory__descriptor;
    IODMACommand_GetPreparation_Rpl_Content content;
};
#pragma pack()
#define IODMACommand_GetPreparation_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IODMACommand_GetPreparation_Msg * message;
#else /* KERNEL */
        const struct IODMACommand_GetPreparation_Msg_With_Content * message;
#endif /* KERNEL */
        struct IODMACommand_GetPreparation_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IODMACommand_GetPreparation_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IODMACommand_GetPreparation_Invocation;
struct IODMACommand_PerformOperation_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  data;
    uint64_t  options;
    uint64_t  dmaOffset;
    uint64_t  length;
    uint64_t  dataOffset;
};
#pragma pack(4)
struct IODMACommand_PerformOperation_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t data__descriptor;
};
struct IODMACommand_PerformOperation_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t data__descriptor;
    IODMACommand_PerformOperation_Msg_Content content;
};
#pragma pack()
#define IODMACommand_PerformOperation_Msg_ObjRefs (2)

struct IODMACommand_PerformOperation_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IODMACommand_PerformOperation_Rpl
{
    IORPCMessageMach           mach;
};
struct IODMACommand_PerformOperation_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IODMACommand_PerformOperation_Rpl_Content content;
};
#pragma pack()
#define IODMACommand_PerformOperation_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IODMACommand_PerformOperation_Msg * message;
#else /* KERNEL */
        const struct IODMACommand_PerformOperation_Msg_With_Content * message;
#endif /* KERNEL */
        struct IODMACommand_PerformOperation_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IODMACommand_PerformOperation_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IODMACommand_PerformOperation_Invocation;
#if !KERNEL
extern OSMetaClass * gOSContainerMetaClass;
extern OSMetaClass * gOSDataMetaClass;
extern OSMetaClass * gOSNumberMetaClass;
extern OSMetaClass * gOSStringMetaClass;
extern OSMetaClass * gOSBooleanMetaClass;
extern OSMetaClass * gOSDictionaryMetaClass;
extern OSMetaClass * gOSArrayMetaClass;
extern OSMetaClass * gOSSetMetaClass;
extern OSMetaClass * gOSOrderedSetMetaClass;
extern OSMetaClass * gIODispatchQueueMetaClass;
extern OSMetaClass * gIOMemoryMapMetaClass;
extern OSMetaClass * gIOBufferMemoryDescriptorMetaClass;
extern OSMetaClass * gIOUserClientMetaClass;
extern OSMetaClass * gOSActionMetaClass;
extern OSMetaClass * gIOServiceStateNotificationDispatchSourceMetaClass;
#endif /* !KERNEL */

#if !KERNEL

#define IODMACommand_QueueNames  ""

#define IODMACommand_MethodNames  ""

#define IODMACommandMetaClass_MethodNames  ""

struct OSClassDescription_IODMACommand_t
{
    OSClassDescription base;
    uint64_t           methodOptions[2 * 0];
    uint64_t           metaMethodOptions[2 * 0];
    char               queueNames[sizeof(IODMACommand_QueueNames)];
    char               methodNames[sizeof(IODMACommand_MethodNames)];
    char               metaMethodNames[sizeof(IODMACommandMetaClass_MethodNames)];
};

const struct OSClassDescription_IODMACommand_t
OSClassDescription_IODMACommand =
{
    .base =
    {
        .descriptionSize         = sizeof(OSClassDescription_IODMACommand_t),
        .name                    = "IODMACommand",
        .superName               = "OSObject",
        .methodOptionsSize       = 2 * sizeof(uint64_t) * 0,
        .methodOptionsOffset     = __builtin_offsetof(struct OSClassDescription_IODMACommand_t, methodOptions),
        .metaMethodOptionsSize   = 2 * sizeof(uint64_t) * 0,
        .metaMethodOptionsOffset = __builtin_offsetof(struct OSClassDescription_IODMACommand_t, metaMethodOptions),
        .queueNamesSize       = sizeof(IODMACommand_QueueNames),
        .queueNamesOffset     = __builtin_offsetof(struct OSClassDescription_IODMACommand_t, queueNames),
        .methodNamesSize         = sizeof(IODMACommand_MethodNames),
        .methodNamesOffset       = __builtin_offsetof(struct OSClassDescription_IODMACommand_t, methodNames),
        .metaMethodNamesSize     = sizeof(IODMACommandMetaClass_MethodNames),
        .metaMethodNamesOffset   = __builtin_offsetof(struct OSClassDescription_IODMACommand_t, metaMethodNames),
        .flags                   = 1*kOSClassCanRemote,
        .resv1                   = {0},
    },
    .methodOptions =
    {
    },
    .metaMethodOptions =
    {
    },
    .queueNames      = IODMACommand_QueueNames,
    .methodNames     = IODMACommand_MethodNames,
    .metaMethodNames = IODMACommandMetaClass_MethodNames,
};

OSMetaClass * gIODMACommandMetaClass;

static kern_return_t
IODMACommand_New(OSMetaClass * instance);

const OSClassLoadInformation
IODMACommand_Class = 
{
    .description       = &OSClassDescription_IODMACommand.base,
    .metaPointer       = &gIODMACommandMetaClass,
    .version           = 1,
    .instanceSize      = sizeof(IODMACommand),

    .resv2             = {0},

    .New               = &IODMACommand_New,
    .resv3             = {0},

};

extern const void * const
gIODMACommand_Declaration;
const void * const
gIODMACommand_Declaration
__attribute__((used,visibility("hidden"),section("__DATA_CONST,__osclassinfo,regular,no_dead_strip"),no_sanitize("address")))
    = &IODMACommand_Class;

static kern_return_t
IODMACommand_New(OSMetaClass * instance)
{
    if (!new(instance) IODMACommandMetaClass) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

kern_return_t
IODMACommandMetaClass::New(OSObject * instance)
{
    if (!new(instance) IODMACommand) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

#endif /* !KERNEL */

#ifdef KERNEL
#define MESSAGE_CONTENT(__field) (messageContent->__field)
#else /* KERNEL */
#define MESSAGE_CONTENT(__field) (message->content.__field)
#endif /* KERNEL */

kern_return_t
IODMACommand::Dispatch(const IORPC rpc)
{
    return _Dispatch(this, rpc);
}

kern_return_t
IODMACommand::_Dispatch(IODMACommand * self, const IORPC rpc)
{
    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {
#if KERNEL
        case IODMACommand_PrepareForDMA_ID:
        {
            ret = IODMACommand::PrepareForDMA_Invoke(rpc, self, SimpleMemberFunctionCast(IODMACommand::PrepareForDMA_Handler, *self, &IODMACommand::PrepareForDMA_Impl));
            break;
        }
#endif /* !KERNEL */
#if KERNEL
        case IODMACommand_CompleteDMA_ID:
        {
            ret = IODMACommand::CompleteDMA_Invoke(rpc, self, SimpleMemberFunctionCast(IODMACommand::CompleteDMA_Handler, *self, &IODMACommand::CompleteDMA_Impl));
            break;
        }
#endif /* !KERNEL */
#if KERNEL
        case IODMACommand_GetPreparation_ID:
        {
            ret = IODMACommand::GetPreparation_Invoke(rpc, self, SimpleMemberFunctionCast(IODMACommand::GetPreparation_Handler, *self, &IODMACommand::GetPreparation_Impl));
            break;
        }
#endif /* !KERNEL */
#if KERNEL
        case IODMACommand_PerformOperation_ID:
        {
            ret = IODMACommand::PerformOperation_Invoke(rpc, self, SimpleMemberFunctionCast(IODMACommand::PerformOperation_Handler, *self, &IODMACommand::PerformOperation_Impl));
            break;
        }
#endif /* !KERNEL */

        default:
            ret = OSObject::_Dispatch(self, rpc);
            break;
    }

    return (ret);
}

#if KERNEL
kern_return_t
IODMACommand::MetaClass::Dispatch(const IORPC rpc)
{
#else /* KERNEL */
kern_return_t
IODMACommandMetaClass::Dispatch(const IORPC rpc)
{
#endif /* !KERNEL */

    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {
#if KERNEL
        case IODMACommand_Create_ID:
            ret = IODMACommand::Create_Invoke(rpc, &IODMACommand::Create_Impl);
            break;
#endif /* !KERNEL */

        default:
            ret = OSMetaClassBase::Dispatch(rpc);
            break;
    }

    return (ret);
}

kern_return_t
IODMACommand::Create(
        IOService * device,
        uint64_t options,
        const IODMACommandSpecification * specification,
        IODMACommand ** command)
{
    kern_return_t ret;
    union
    {
        IODMACommand_Create_Msg_With_Content msg;
        struct
        {
            IODMACommand_Create_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IODMACommand_Create_Msg_With_Content * msg = &buf.msg;
    struct IODMACommand_Create_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IODMACommand_Create_ID;
    msg->content.__object = (OSObjectRef) OSTypeID(IODMACommand);
    msg->content.__hdr.objectRefs = IODMACommand_Create_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 2;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->device__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.device = (OSObjectRef) device;

    msg->content.options = options;

    msg->content.specification = *specification;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    ret = OSMTypeID(IODMACommand)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IODMACommand_Create_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IODMACommand_Create_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        *command = OSDynamicCast(IODMACommand, (OSObject *) rpl->content.command);
        if (rpl->content.command && !*command) ret = kIOReturnBadArgument;
    }


    return (ret);
}

kern_return_t
IODMACommand::PrepareForDMA(
        uint64_t options,
        IOMemoryDescriptor * memory,
        uint64_t offset,
        uint64_t length,
        uint64_t * flags,
        uint32_t * segmentsCount,
        IOAddressSegment * segments,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IODMACommand_PrepareForDMA_Msg_With_Content msg;
        struct
        {
            IODMACommand_PrepareForDMA_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IODMACommand_PrepareForDMA_Msg_With_Content * msg = &buf.msg;
    struct IODMACommand_PrepareForDMA_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IODMACommand_PrepareForDMA_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IODMACommand_PrepareForDMA_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 2;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->content.options = options;

    msg->memory__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.memory = (OSObjectRef) memory;

    msg->content.offset = offset;

    msg->content.length = length;

    if (*segmentsCount > (sizeof(rpl->content.__segments) / sizeof(rpl->content.__segments[0]))) return kIOReturnOverrun;
    msg->content.segmentsCount = *segmentsCount;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IODMACommand_PrepareForDMA_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IODMACommand_PrepareForDMA_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        if (flags) *flags = rpl->content.flags;
        if (rpl->content.segmentsCount < *segmentsCount) *segmentsCount = rpl->content.segmentsCount;
        bcopy(&rpl->content.__segments[0], segments, *segmentsCount * sizeof(rpl->content.__segments[0]));
    }


    return (ret);
}

kern_return_t
IODMACommand::CompleteDMA(
        uint64_t options,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IODMACommand_CompleteDMA_Msg_With_Content msg;
        struct
        {
            IODMACommand_CompleteDMA_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IODMACommand_CompleteDMA_Msg_With_Content * msg = &buf.msg;
    struct IODMACommand_CompleteDMA_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IODMACommand_CompleteDMA_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IODMACommand_CompleteDMA_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->content.options = options;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IODMACommand_CompleteDMA_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IODMACommand_CompleteDMA_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
    }


    return (ret);
}

kern_return_t
IODMACommand::GetPreparation(
        uint64_t * offset,
        uint64_t * length,
        IOMemoryDescriptor ** memory,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IODMACommand_GetPreparation_Msg_With_Content msg;
        struct
        {
            IODMACommand_GetPreparation_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IODMACommand_GetPreparation_Msg_With_Content * msg = &buf.msg;
    struct IODMACommand_GetPreparation_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IODMACommand_GetPreparation_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IODMACommand_GetPreparation_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IODMACommand_GetPreparation_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IODMACommand_GetPreparation_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        if (offset) *offset = rpl->content.offset;
        if (length) *length = rpl->content.length;
        *memory = OSDynamicCast(IOMemoryDescriptor, (OSObject *) rpl->content.memory);
        if (rpl->content.memory && !*memory) ret = kIOReturnBadArgument;
    }


    return (ret);
}

kern_return_t
IODMACommand::PerformOperation(
        uint64_t options,
        uint64_t dmaOffset,
        uint64_t length,
        uint64_t dataOffset,
        IOMemoryDescriptor * data,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IODMACommand_PerformOperation_Msg_With_Content msg;
        struct
        {
            IODMACommand_PerformOperation_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IODMACommand_PerformOperation_Msg_With_Content * msg = &buf.msg;
    struct IODMACommand_PerformOperation_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IODMACommand_PerformOperation_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IODMACommand_PerformOperation_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 2;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->content.options = options;

    msg->content.dmaOffset = dmaOffset;

    msg->content.length = length;

    msg->content.dataOffset = dataOffset;

    msg->data__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.data = (OSObjectRef) data;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IODMACommand_PerformOperation_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IODMACommand_PerformOperation_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
    }


    return (ret);
}

kern_return_t
IODMACommand::Create_Invoke(const IORPC _rpc,
        Create_Handler func)
{
    IODMACommand_Create_Invocation rpc = { _rpc };
    IODMACommand_Create_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IODMACommand_Create_Msg *         message = rpc.message;
    const IODMACommand_Create_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IODMACommand_Create_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    IOService * device;

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IODMACommand_Create_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IODMACommand_Create_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    device = OSDynamicCast(IOService, (OSObject *) MESSAGE_CONTENT(device));
    if (!device && MESSAGE_CONTENT(device)) return (kIOReturnBadArgument);

    ret = (*func)(        device,
        MESSAGE_CONTENT(options),
        &MESSAGE_CONTENT(specification),
        (IODMACommand **)&reply->content.command);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IODMACommand_Create_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IODMACommand_Create_Rpl_ObjRefs;
    reply->command__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    return (ret);
}

kern_return_t
IODMACommand::PrepareForDMA_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        PrepareForDMA_Handler func)
{
    IODMACommand_PrepareForDMA_Invocation rpc = { _rpc };
    IODMACommand_PrepareForDMA_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IODMACommand_PrepareForDMA_Msg *         message = rpc.message;
    const IODMACommand_PrepareForDMA_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IODMACommand_PrepareForDMA_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    IOMemoryDescriptor * memory;
    unsigned int segmentsCount = (sizeof(reply->content.__segments) / sizeof(reply->content.__segments[0]));
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wtautological-unsigned-zero-compare"
    if (MESSAGE_CONTENT(segmentsCount) >= 0 && segmentsCount > MESSAGE_CONTENT(segmentsCount)) segmentsCount = MESSAGE_CONTENT(segmentsCount);
#pragma clang diagnostic pop

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IODMACommand_PrepareForDMA_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IODMACommand_PrepareForDMA_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    memory = OSDynamicCast(IOMemoryDescriptor, (OSObject *) MESSAGE_CONTENT(memory));
    if (!memory && MESSAGE_CONTENT(memory)) return (kIOReturnBadArgument);

    ret = (*func)(target,
        MESSAGE_CONTENT(options),
        memory,
        MESSAGE_CONTENT(offset),
        MESSAGE_CONTENT(length),
        &reply->content.flags,
        &segmentsCount,
        &reply->content.__segments[0]);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IODMACommand_PrepareForDMA_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IODMACommand_PrepareForDMA_Rpl_ObjRefs;
    reply->content.segmentsCount = segmentsCount;

    return (ret);
}

kern_return_t
IODMACommand::CompleteDMA_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        CompleteDMA_Handler func)
{
    IODMACommand_CompleteDMA_Invocation rpc = { _rpc };
    IODMACommand_CompleteDMA_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IODMACommand_CompleteDMA_Msg *         message = rpc.message;
    const IODMACommand_CompleteDMA_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IODMACommand_CompleteDMA_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IODMACommand_CompleteDMA_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IODMACommand_CompleteDMA_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);

    ret = (*func)(target,
        MESSAGE_CONTENT(options));

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IODMACommand_CompleteDMA_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IODMACommand_CompleteDMA_Rpl_ObjRefs;

    return (ret);
}

kern_return_t
IODMACommand::GetPreparation_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        GetPreparation_Handler func)
{
    IODMACommand_GetPreparation_Invocation rpc = { _rpc };
    IODMACommand_GetPreparation_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IODMACommand_GetPreparation_Msg *         message = rpc.message;
    const IODMACommand_GetPreparation_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IODMACommand_GetPreparation_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IODMACommand_GetPreparation_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IODMACommand_GetPreparation_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);

    ret = (*func)(target,
        &reply->content.offset,
        &reply->content.length,
        (IOMemoryDescriptor **)&reply->content.memory);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IODMACommand_GetPreparation_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IODMACommand_GetPreparation_Rpl_ObjRefs;
    reply->memory__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    return (ret);
}

kern_return_t
IODMACommand::PerformOperation_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        PerformOperation_Handler func)
{
    IODMACommand_PerformOperation_Invocation rpc = { _rpc };
    IODMACommand_PerformOperation_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IODMACommand_PerformOperation_Msg *         message = rpc.message;
    const IODMACommand_PerformOperation_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IODMACommand_PerformOperation_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    IOMemoryDescriptor * data;

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IODMACommand_PerformOperation_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IODMACommand_PerformOperation_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    data = OSDynamicCast(IOMemoryDescriptor, (OSObject *) MESSAGE_CONTENT(data));
    if (!data && MESSAGE_CONTENT(data)) return (kIOReturnBadArgument);

    ret = (*func)(target,
        MESSAGE_CONTENT(options),
        MESSAGE_CONTENT(dmaOffset),
        MESSAGE_CONTENT(length),
        MESSAGE_CONTENT(dataOffset),
        data);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IODMACommand_PerformOperation_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IODMACommand_PerformOperation_Rpl_ObjRefs;

    return (ret);
}



